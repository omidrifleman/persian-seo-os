"""Gold ezafe corpus helpers: schema, tokenize, load, worksheet I/O, metrics."""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ZWNJ = "\u200c"

# Minimum strata quotas (part 2).
STRATA_QUOTAS: dict[str, int] = {
    "zwnj": 30,
    "plural_ha": 30,
    "ye_non_ezafe": 25,
    "no_ezafe_candidate": 25,
    "latin_brand": 20,
    "number_unit": 20,
}

_SENT_SPLIT = re.compile(r"(?<=[.!?؟۔\n])\s+")
_WORD_SPLIT = re.compile(r"\s+")
# Keep internal ZWNJ; peel ASCII/Persian punctuation from edges.
_EDGE_PUNCT = re.compile(r"^[\s\"'«»\(\)\[\]\{\}،,؛;:]+|[\s\"'«»\(\)\[\]\{\}،,؛;.!?؟۔]+$")


MIN_EVAL_EXAMPLES = 20
ALIGNMENT_FAIL_THRESHOLD = 0.10
MIN_ECOMMERCE_TARGET = 40

# Fine source_kind buckets (record-level).
SOURCE_KIND_WIKI = "wiki"
SOURCE_KIND_NEWS = "news"
SOURCE_KIND_MAGAZINE = "magazine"
SOURCE_KIND_ECOMMERCE = "ecommerce"
SOURCE_KINDS = frozenset(
    {SOURCE_KIND_WIKI, SOURCE_KIND_NEWS, SOURCE_KIND_MAGAZINE, SOURCE_KIND_ECOMMERCE}
)
# Back-compat alias used by older code/tests.
SOURCE_KIND_WIKIPEDIA = SOURCE_KIND_WIKI
SOURCE_KIND_COMMERCIAL = "commercial"  # rollup only (not stored)

TOKENIZER_SOURCE_DADMA = "dadmatools"

DOMAIN_SOURCE_KIND: dict[str, str] = {
    "fa.wikipedia.org": SOURCE_KIND_WIKI,
    "hamshahrionline.ir": SOURCE_KIND_NEWS,
    "isna.ir": SOURCE_KIND_NEWS,
    "khabaronline.ir": SOURCE_KIND_NEWS,
    "digiato.com": SOURCE_KIND_MAGAZINE,
    "tarafdari.com": SOURCE_KIND_MAGAZINE,
    "zoomit.ir": SOURCE_KIND_MAGAZINE,
    "digikala.com": SOURCE_KIND_ECOMMERCE,
    "blog.okala.com": SOURCE_KIND_ECOMMERCE,
    "okala.com": SOURCE_KIND_ECOMMERCE,
    "basalam.com": SOURCE_KIND_ECOMMERCE,
    "emalls.ir": SOURCE_KIND_ECOMMERCE,
    "torob.com": SOURCE_KIND_ECOMMERCE,
    "modiseh.com": SOURCE_KIND_ECOMMERCE,
}


@dataclass(frozen=True)
class GoldExample:
    id: str
    text: str
    tokens: tuple[str, ...]
    char_spans: tuple[tuple[int, int], ...]
    ezafe: tuple[int, ...] | None = None
    note: str = ""
    verified: bool = False
    ambiguous: bool = False
    strata: tuple[str, ...] = ()
    source: str = ""
    source_kind: str = ""
    source_url: str = ""
    license: str = ""
    collected_at: str = ""
    page_title: str = ""
    revision_id: str = ""
    labeled_by: str = ""
    labeled_at: str = ""
    tokenizer_source: str = ""
    dadmatools_version: str = ""
    tokens_minted_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tokens:
            raise ValueError(f"gold id={self.id!r}: tokens must be non-empty")
        if len(self.char_spans) != len(self.tokens):
            raise ValueError(
                f"gold id={self.id!r}: len(char_spans)={len(self.char_spans)} "
                f"!= len(tokens)={len(self.tokens)}"
            )
        for i, ((start, end), tok) in enumerate(
            zip(self.char_spans, self.tokens, strict=True)
        ):
            if not (0 <= start < end <= len(self.text)):
                raise ValueError(
                    f"gold id={self.id!r} token_index={i}: bad char_span "
                    f"[{start}, {end}) for text_len={len(self.text)}"
                )
            slice_ = self.text[start:end]
            if slice_ != tok:
                raise ValueError(
                    f"gold id={self.id!r} token_index={i}: char_span text "
                    f"{slice_!r} != token {tok!r}"
                )
        if self.ezafe is not None:
            if len(self.tokens) != len(self.ezafe):
                raise ValueError(
                    f"gold id={self.id!r}: len(tokens)={len(self.tokens)} "
                    f"!= len(ezafe)={len(self.ezafe)}"
                )
            if any(v not in (0, 1) for v in self.ezafe):
                raise ValueError(
                    f"gold id={self.id!r}: ezafe must be 0/1 only, got {self.ezafe!r}"
                )


@dataclass(frozen=True)
class BinaryCounts:
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def support_positive(self) -> int:
        return self.tp + self.fn

    @property
    def precision(self) -> float | None:
        denom = self.tp + self.fp
        if denom == 0:
            return None
        return self.tp / denom

    @property
    def recall(self) -> float | None:
        denom = self.tp + self.fn
        if denom == 0:
            return None
        return self.tp / denom

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def canonical_domain(url: str) -> str:
    """Host without leading www.; empty if URL unparsable."""
    host = (urlparse(url).netloc or "").lower().strip()
    return host.removeprefix("www.")


def whitespace_word_count(text: str) -> int:
    return len([w for w in _WORD_SPLIT.split(text.strip()) if w])


def split_sentences(text: str) -> list[str]:
    parts = _SENT_SPLIT.split(text.replace("\r\n", "\n").replace("\r", "\n"))
    out: list[str] = []
    for part in parts:
        s = re.sub(r"\s+", " ", part).strip()
        if s:
            out.append(s)
    return out


def tokenize_raw(text: str) -> list[str]:
    """Deterministic raw tokens for worksheets (not Dadma). Keeps internal ZWNJ."""
    tokens: list[str] = []
    for piece in _WORD_SPLIT.split(text.strip()):
        if not piece:
            continue
        tok = _EDGE_PUNCT.sub("", piece)
        if tok:
            tokens.append(tok)
    return tokens


def detect_strata(text: str) -> list[str]:
    """Heuristic strata tags for sampling quotas (not gold labels)."""
    tags: list[str] = []
    if ZWNJ in text:
        tags.append("zwnj")
    if re.search(r"(?<!\w)ها(ی)?(?!\w)|ها\b|های\b", text) or "ها" in text or "های" in text:
        tags.append("plural_ha")
    if re.search(r"ی\s+که|یی(?:\s|$)|یک\s+\S+ی(?:\s|$)|(?:^|\s)\S+ی\s+را(?:\s|$)", text):
        tags.append("ye_non_ezafe")
    if re.search(r"[A-Za-z]", text):
        tags.append("latin_brand")
    if re.search(r"[\d۰-۹٠-٩]|٪|٪|کیلو|گرم|متر|سانتی|میلی|لیتر|تومان|ریال", text):
        tags.append("number_unit")
    # Pure-negative *candidate*: short clause-like, no obvious genitive izafe chain cue.
    # Final membership still requires human labels; this only fills sampling quota.
    words = whitespace_word_count(text)
    # Prefer SV-ish without long NPs: has a light verb-ish ending.
    if (
        5 <= words <= 10
        and not re.search(r"\s+(ی|ِ)\s+", text)
        and re.search(r"(است|بود|شد|رفت|آمد|کرد|نمود|می‌\w+|مي\w+)\s*[.!?؟۔]?$", text)
    ):
        tags.append("no_ezafe_candidate")
    return tags


def align_token_char_spans(text: str, tokens: Iterable[str]) -> tuple[tuple[int, int], ...]:
    """Map token strings onto original `text` in order (character offsets).

    Dadma/spaCy may insert spaces in its internal Doc.text; spans must land on
    the raw gold `text` so labels survive tokenizer version changes.
    """
    spans: list[tuple[int, int]] = []
    pos = 0
    for i, tok in enumerate(tokens):
        if not tok:
            raise ValueError(f"empty token at index {i}")
        # Prefer match at/after current cursor; skip intervening whitespace.
        search_from = pos
        while search_from < len(text) and text[search_from].isspace():
            search_from += 1
        if text.startswith(tok, search_from):
            start = search_from
        else:
            start = text.find(tok, pos)
            if start < 0:
                raise ValueError(
                    f"cannot align token_index={i} {tok!r} in text={text!r} "
                    f"after pos={pos}"
                )
        end = start + len(tok)
        spans.append((start, end))
        pos = end
    return tuple(spans)


def installed_dadmatools_version() -> str:
    try:
        from importlib.metadata import version

        return version("dadmatools")
    except Exception:  # noqa: BLE001 — report unknown rather than crash mint path
        return "unknown"


def resolve_source_kind(*, source: str, source_kind: str = "", source_url: str = "") -> str:
    """Map legacy buckets / domains onto wiki|news|magazine|ecommerce."""
    if source_kind in SOURCE_KINDS:
        return source_kind
    # Legacy bucket names.
    legacy = {
        "wikipedia": SOURCE_KIND_WIKI,
        "fa.wikipedia": SOURCE_KIND_WIKI,
        "news_portal": SOURCE_KIND_NEWS,
        "blog_portal": SOURCE_KIND_MAGAZINE,
        "shop_mag": SOURCE_KIND_ECOMMERCE,
        "shop_wiki_stub": SOURCE_KIND_ECOMMERCE,
    }
    if source_kind in legacy:
        return legacy[source_kind]
    if source in legacy:
        return legacy[source]
    domain = source if "." in source else canonical_domain(source_url)
    if domain in DOMAIN_SOURCE_KIND:
        return DOMAIN_SOURCE_KIND[domain]
    if "wikipedia" in (source or "") or "wikipedia" in domain:
        return SOURCE_KIND_WIKI
    # Incomplete fixtures / legacy stubs — do not invent commercial kind.
    if not source and not source_url and not source_kind:
        return SOURCE_KIND_MAGAZINE
    raise ValueError(
        f"cannot resolve source_kind for source={source!r} "
        f"source_kind={source_kind!r} url={source_url!r}"
    )


def is_wikipedia_example(ex: GoldExample) -> bool:
    kind = ex.source_kind or resolve_source_kind(
        source=ex.source, source_kind=ex.source_kind, source_url=ex.source_url
    )
    if kind == SOURCE_KIND_WIKI:
        return True
    if ex.source in {"fa.wikipedia", "fa.wikipedia.org"}:
        return True
    return "wikipedia.org" in (ex.source or "")


def is_commercial_example(ex: GoldExample) -> bool:
    return not is_wikipedia_example(ex)


def example_to_json(ex: GoldExample) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": ex.id,
        "text": ex.text,
        "tokens": list(ex.tokens),
        "char_spans": [list(span) for span in ex.char_spans],
        "ezafe": None if ex.ezafe is None else list(ex.ezafe),
        "note": ex.note,
        "verified": ex.verified,
        "ambiguous": ex.ambiguous,
        "strata": list(ex.strata),
        "source": ex.source,
        "source_kind": ex.source_kind,
        "source_url": ex.source_url,
        "license": ex.license,
        "collected_at": ex.collected_at,
        "page_title": ex.page_title,
        "revision_id": ex.revision_id,
        "labeled_by": ex.labeled_by,
        "labeled_at": ex.labeled_at,
        "tokenizer_source": ex.tokenizer_source,
        "dadmatools_version": ex.dadmatools_version,
        "tokens_minted_at": ex.tokens_minted_at,
    }
    row.update(ex.extra)
    return row


def example_from_json(raw: dict[str, Any]) -> GoldExample:
    ezafe_raw = raw.get("ezafe", None)
    ezafe: tuple[int, ...] | None
    if ezafe_raw is None:
        ezafe = None
    else:
        ezafe = tuple(int(v) for v in ezafe_raw)
    tokens = tuple(str(t) for t in raw["tokens"])
    text = str(raw["text"])
    spans_raw = raw.get("char_spans")
    if spans_raw is None:
        # Legacy rows: derive spans from tokens (must still match text).
        char_spans = align_token_char_spans(text, tokens)
    else:
        char_spans = tuple((int(a), int(b)) for a, b in spans_raw)
    known = {
        "id",
        "text",
        "tokens",
        "char_spans",
        "ezafe",
        "note",
        "verified",
        "ambiguous",
        "strata",
        "source",
        "source_kind",
        "source_url",
        "license",
        "collected_at",
        "page_title",
        "revision_id",
        "labeled_by",
        "labeled_at",
        "tokenizer_source",
        "dadmatools_version",
        "tokens_minted_at",
    }
    extra = {k: v for k, v in raw.items() if k not in known}
    source = str(raw.get("source", ""))
    source_url = str(raw.get("source_url", ""))
    source_kind = resolve_source_kind(
        source=source,
        source_kind=str(raw.get("source_kind", "") or ""),
        source_url=source_url,
    )
    return GoldExample(
        id=str(raw["id"]),
        text=text,
        tokens=tokens,
        char_spans=char_spans,
        ezafe=ezafe,
        note=str(raw.get("note", "")),
        verified=bool(raw.get("verified", False)),
        ambiguous=bool(raw.get("ambiguous", False)),
        strata=tuple(str(s) for s in raw.get("strata", []) or []),
        source=source,
        source_kind=source_kind,
        source_url=source_url,
        license=str(raw.get("license", "")),
        collected_at=str(raw.get("collected_at", "")),
        page_title=str(raw.get("page_title", "")),
        revision_id=str(raw.get("revision_id", "")),
        labeled_by=str(raw.get("labeled_by", "")),
        labeled_at=str(raw.get("labeled_at", "")),
        tokenizer_source=str(raw.get("tokenizer_source", "")),
        dadmatools_version=str(raw.get("dadmatools_version", "")),
        tokens_minted_at=str(raw.get("tokens_minted_at", "")),
        extra=extra,
    )


def load_ezafe_gold(
    path: str | Path,
    *,
    require_labeled: bool = True,
) -> list[GoldExample]:
    """Load JSONL gold file. Missing/empty → clear error (no fake metrics)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(
            f"Ezafe gold file missing: {p}. Create data/gold/ezafe_gold.jsonl "
            "with human-verified labels before running evaluation."
        )
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(
            f"Ezafe gold file is empty: {p}. Refusing to print fabricated metrics."
        )
    examples: list[GoldExample] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            raw: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {p}:{line_no}: {exc}") from exc
        examples.append(example_from_json(raw))
    if not examples:
        raise ValueError(
            f"Ezafe gold file has no examples: {p}. Refusing to print fabricated metrics."
        )
    if require_labeled:
        labeled = [
            ex
            for ex in examples
            if ex.verified and ex.ezafe is not None and not ex.ambiguous
        ]
        if not labeled:
            raise ValueError(
                f"No verified non-ambiguous labeled examples in {p}. "
                "Complete human labeling via worksheet ingest first."
            )
        return labeled
    return examples


def write_ezafe_gold(path: str | Path, examples: Iterable[GoldExample]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(example_to_json(ex), ensure_ascii=False) for ex in examples]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def confusion_counts(gold: Iterable[int], pred: Iterable[int]) -> BinaryCounts:
    g = list(gold)
    p = list(pred)
    if len(g) != len(p):
        raise ValueError(f"length mismatch gold={len(g)} pred={len(p)}")
    tp = fp = tn = fn = 0
    for gv, pv in zip(g, p, strict=True):
        if gv not in (0, 1) or pv not in (0, 1):
            raise ValueError(f"labels must be 0/1, got gold={gv!r} pred={pv!r}")
        if gv == 1 and pv == 1:
            tp += 1
        elif gv == 0 and pv == 1:
            fp += 1
        elif gv == 0 and pv == 0:
            tn += 1
        else:
            fn += 1
    return BinaryCounts(tp=tp, fp=fp, tn=tn, fn=fn)


def format_metrics_report(counts: BinaryCounts, *, n_examples: int, n_tokens: int) -> str:
    payload = metrics_slice_payload(counts, n_examples=n_examples, n_tokens=n_tokens)
    if payload["status"] == "insufficient_sample":
        return "insufficient_sample"
    def fmt(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.4f}"

    return "\n".join(
        [
            f"examples={n_examples} tokens={n_tokens}",
            f"confusion tp={counts.tp} fp={counts.fp} tn={counts.tn} fn={counts.fn}",
            (
                f"precision={fmt(counts.precision)} recall={fmt(counts.recall)} "
                f"f1={fmt(counts.f1)}"
            ),
        ]
    )


def metrics_slice_payload(
    counts: BinaryCounts,
    *,
    n_examples: int,
    n_tokens: int,
    min_examples: int = MIN_EVAL_EXAMPLES,
) -> dict[str, Any]:
    """Eval slice payload. Small slices → insufficient_sample (no F1 numbers)."""
    if n_examples < min_examples:
        return {"status": "insufficient_sample"}
    return {
        "status": "ok",
        "n_examples": n_examples,
        "n_tokens": n_tokens,
        "tp": counts.tp,
        "fp": counts.fp,
        "tn": counts.tn,
        "fn": counts.fn,
        "precision": counts.precision,
        "recall": counts.recall,
        "f1": counts.f1,
    }


def tokens_aligned(ours: Iterable[str], model: Iterable[str]) -> bool:
    return list(ours) == list(model)


def classify_alignment_mismatch(ours: list[str], model: list[str]) -> str:
    """Dominant mismatch bucket for reporting (not a gold label)."""
    if tokens_aligned(ours, model):
        return "aligned"
    o_join = "".join(ours)
    m_join = "".join(model)
    punct = set(".,!?;:،؛؟۔«»\"'()[]{}…-_/")
    if any(ch in punct for ch in o_join + m_join) and re.sub(
        r"[^\w\u0600-\u06FF\u200c]+", "", o_join, flags=re.UNICODE
    ) == re.sub(r"[^\w\u0600-\u06FF\u200c]+", "", m_join, flags=re.UNICODE):
        return "punctuation"
    if (ZWNJ in o_join) != (ZWNJ in m_join) or any(
        (ZWNJ in a) != (ZWNJ in b) for a, b in zip(ours, model, strict=False)
    ):
        return "zwnj"
    if re.search(r"[\d۰-۹٠-٩]", o_join + m_join):
        return "number"
    if re.search(r"[A-Za-z]", o_join + m_join):
        return "latin"
    return "other"


def with_replaced_tokens(ex: GoldExample, tokens: tuple[str, ...]) -> GoldExample:
    """Replace token boundaries only; never copies ezafe labels from a model."""
    spans = align_token_char_spans(ex.text, tokens)
    return GoldExample(
        id=ex.id,
        text=ex.text,
        tokens=tokens,
        char_spans=spans,
        ezafe=None if ex.ezafe is None else ex.ezafe,
        note=ex.note,
        verified=ex.verified,
        ambiguous=ex.ambiguous,
        strata=ex.strata,
        source=ex.source,
        source_kind=ex.source_kind,
        source_url=ex.source_url,
        license=ex.license,
        collected_at=ex.collected_at,
        page_title=ex.page_title,
        revision_id=ex.revision_id,
        labeled_by=ex.labeled_by,
        labeled_at=ex.labeled_at,
        tokenizer_source=ex.tokenizer_source,
        dadmatools_version=ex.dadmatools_version,
        tokens_minted_at=ex.tokens_minted_at,
        extra=dict(ex.extra),
    )


def with_source_fields(
    ex: GoldExample,
    *,
    source: str,
    source_kind: str,
) -> GoldExample:
    return GoldExample(
        id=ex.id,
        text=ex.text,
        tokens=ex.tokens,
        char_spans=ex.char_spans,
        ezafe=ex.ezafe,
        note=ex.note,
        verified=ex.verified,
        ambiguous=ex.ambiguous,
        strata=ex.strata,
        source=source,
        source_kind=source_kind,
        source_url=ex.source_url,
        license=ex.license,
        collected_at=ex.collected_at,
        page_title=ex.page_title,
        revision_id=ex.revision_id,
        labeled_by=ex.labeled_by,
        labeled_at=ex.labeled_at,
        tokenizer_source=ex.tokenizer_source,
        dadmatools_version=ex.dadmatools_version,
        tokens_minted_at=ex.tokens_minted_at,
        extra=dict(ex.extra),
    )


def mint_dadma_tokens(
    text: str,
    *,
    token_strings: Iterable[str],
    minted_at: str | None = None,
    version: str | None = None,
) -> tuple[tuple[str, ...], tuple[tuple[int, int], ...], str, str, str]:
    """Build tokens + char_spans + mint metadata (no ezafe labels)."""
    tokens = tuple(token_strings)
    spans = align_token_char_spans(text, tokens)
    return (
        tokens,
        spans,
        TOKENIZER_SOURCE_DADMA,
        version or installed_dadmatools_version(),
        minted_at or utc_now_iso(),
    )


def verify_example_tokens_against_model(
    ex: GoldExample,
    *,
    model_tokens: list[str],
) -> list[str]:
    """Return list of mismatch reasons (empty = ok). Does not use ezafe labels."""
    problems: list[str] = []
    if list(ex.tokens) != model_tokens:
        problems.append("tokens_mismatch")
    try:
        fresh_spans = align_token_char_spans(ex.text, model_tokens)
    except ValueError as exc:
        problems.append(f"align_failed:{exc}")
        return problems
    if tuple(ex.char_spans) != fresh_spans:
        problems.append("char_spans_mismatch")
    for i, ((start, end), tok) in enumerate(zip(ex.char_spans, ex.tokens, strict=True)):
        if ex.text[start:end] != tok:
            problems.append(f"span_slice_mismatch@{i}")
            break
    return problems


def sample_stratified_labeling_batch(
    examples: list[GoldExample],
    *,
    n_wiki: int = 25,
    n_commercial: int = 25,
    seed: int = 20260728,
) -> list[GoldExample]:
    """Pick a balanced labeling batch with strata coverage; deterministic seed."""
    import random

    rng = random.Random(seed)
    wiki = [ex for ex in examples if is_wikipedia_example(ex)]
    commercial = [ex for ex in examples if is_commercial_example(ex)]
    rng.shuffle(wiki)
    rng.shuffle(commercial)

    def pick(pool: list[GoldExample], n: int) -> list[GoldExample]:
        selected: list[GoldExample] = []
        used: set[str] = set()
        filled = {k: 0 for k in STRATA_QUOTAS}
        # Cover strata first (greedy).
        changed = True
        while changed and len(selected) < n:
            changed = False
            need = [k for k, q in STRATA_QUOTAS.items() if filled[k] < max(1, q // 6)]
            for stratum in need or list(STRATA_QUOTAS):
                for cand in pool:
                    if cand.id in used:
                        continue
                    if stratum in cand.strata:
                        selected.append(cand)
                        used.add(cand.id)
                        for s in cand.strata:
                            if s in filled:
                                filled[s] += 1
                        changed = True
                        break
                if len(selected) >= n:
                    break
        for cand in pool:
            if len(selected) >= n:
                break
            if cand.id not in used:
                selected.append(cand)
                used.add(cand.id)
        return selected[:n]

    return pick(wiki, n_wiki) + pick(commercial, n_commercial)


def evaluate_metric_splits(
    examples: list[GoldExample],
    *,
    predictions: dict[str, list[int]],
) -> dict[str, Any]:
    """Build overall / by_source / by_strata metrics from gold + pred flags.

    `predictions` maps example id -> list[int] ezafe flags aligned to tokens.
    """
    overall_pairs: list[tuple[list[int], list[int]]] = []
    by_source: dict[str, list[tuple[list[int], list[int]]]] = defaultdict(list)
    by_strata: dict[str, list[tuple[list[int], list[int]]]] = defaultdict(list)

    for ex in examples:
        if ex.ezafe is None:
            raise ValueError(f"example {ex.id!r} has no ezafe labels")
        if ex.id not in predictions:
            raise ValueError(f"missing prediction for id={ex.id!r}")
        pred = predictions[ex.id]
        if len(pred) != len(ex.ezafe):
            raise ValueError(
                f"id={ex.id!r}: pred len {len(pred)} != gold len {len(ex.ezafe)}"
            )
        pair = (list(ex.ezafe), list(pred))
        overall_pairs.append(pair)
        rollup = "wikipedia" if is_wikipedia_example(ex) else "commercial"
        by_source[rollup].append(pair)
        by_source[f"domain:{ex.source}"].append(pair)
        for s in ex.strata or ("(none)",):
            by_strata[s].append(pair)

    def pack(pairs: list[tuple[list[int], list[int]]]) -> dict[str, Any]:
        if not pairs:
            return metrics_slice_payload(
                BinaryCounts(0, 0, 0, 0), n_examples=0, n_tokens=0
            )
        gold_all: list[int] = []
        pred_all: list[int] = []
        for g, p in pairs:
            gold_all.extend(g)
            pred_all.extend(p)
        counts = confusion_counts(gold_all, pred_all)
        return metrics_slice_payload(
            counts, n_examples=len(pairs), n_tokens=len(gold_all)
        )

    return {
        "overall": pack(overall_pairs),
        "by_source": {k: pack(v) for k, v in sorted(by_source.items())},
        "by_strata": {k: pack(v) for k, v in sorted(by_strata.items())},
    }


WORKSHEET_FIELDS = [
    "id",
    "token_index",
    "token",
    "ezafe",
    "ambiguous",
]


def make_worksheet_rows(examples: Iterable[GoldExample]) -> list[dict[str, str]]:
    """Sentence header row + one token row; ezafe/ambiguous left blank (blind)."""
    rows: list[dict[str, str]] = []
    for ex in examples:
        rows.append(
            {
                "id": ex.id,
                "token_index": "",
                "token": ex.text,
                "ezafe": "",
                "ambiguous": "",
            }
        )
        for i, tok in enumerate(ex.tokens):
            rows.append(
                {
                    "id": ex.id,
                    "token_index": str(i),
                    "token": tok,
                    "ezafe": "",  # NEVER pre-fill from a model
                    "ambiguous": "",
                }
            )
    return rows


def write_worksheet_csv(path: str | Path, examples: Iterable[GoldExample]) -> int:
    """UTF-8 with BOM for Excel on Windows. Returns data row count (incl. headers)."""
    rows = make_worksheet_rows(examples)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=WORKSHEET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def ingest_worksheet_csv(
    path: str | Path,
    *,
    base_examples: dict[str, GoldExample],
    labeled_by: str,
    labeled_at: str | None = None,
) -> list[GoldExample]:
    """Merge human labels into gold examples. Strict validation; no auto-fix."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Worksheet missing: {p}")
    stamped = labeled_at or utc_now_iso()
    with p.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Worksheet has no header: {p}")
        missing = [c for c in ("id", "token_index", "token", "ezafe") if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Worksheet missing columns {missing}: {p}")

        by_id: dict[str, list[tuple[int, str, str, str]]] = {}
        for line_no, row in enumerate(reader, start=2):  # header is line 1
            eid = (row.get("id") or "").strip()
            if not eid:
                raise ValueError(f"Worksheet line {line_no}: empty id")
            idx_raw = (row.get("token_index") or "").strip()
            if idx_raw == "":
                # Sentence context header row — not a label target.
                continue
            try:
                idx = int(idx_raw)
            except ValueError as exc:
                raise ValueError(
                    f"Worksheet line {line_no}: token_index must be int or empty"
                ) from exc
            tok = row.get("token") or ""
            lab = (row.get("ezafe") or "").strip()
            amb = (row.get("ambiguous") or "").strip().lower()
            by_id.setdefault(eid, []).append((idx, tok, lab, amb))

    out: list[GoldExample] = []
    for eid, cells in by_id.items():
        if eid not in base_examples:
            raise ValueError(f"Worksheet id {eid!r} not found in base gold set")
        base = base_examples[eid]
        cells_sorted = sorted(cells, key=lambda x: x[0])
        if [c[0] for c in cells_sorted] != list(range(len(base.tokens))):
            raise ValueError(
                f"Worksheet id {eid!r}: token_index sequence must be "
                f"0..{len(base.tokens) - 1}"
            )
        labels: list[int] = []
        ambiguous = False
        for idx, tok, lab, amb in cells_sorted:
            if tok != base.tokens[idx]:
                raise ValueError(
                    f"Worksheet id {eid!r} token_index={idx}: token text mismatch "
                    f"worksheet={tok!r} gold={base.tokens[idx]!r}"
                )
            if amb in {"1", "true", "yes", "y"}:
                ambiguous = True
            if lab not in {"0", "1"}:
                raise ValueError(
                    f"Worksheet id {eid!r} token_index={idx}: ezafe must be 0 or 1, "
                    f"got {lab!r}"
                )
            labels.append(int(lab))
        if len(labels) != len(base.tokens):
            raise ValueError(
                f"Worksheet id {eid!r}: label length {len(labels)} != "
                f"token length {len(base.tokens)}"
            )
        out.append(
            GoldExample(
                id=base.id,
                text=base.text,
                tokens=base.tokens,
                char_spans=base.char_spans,
                ezafe=tuple(labels),
                note=base.note,
                verified=True,
                ambiguous=ambiguous,
                strata=base.strata,
                source=base.source,
                source_kind=base.source_kind,
                source_url=base.source_url,
                license=base.license,
                collected_at=base.collected_at,
                page_title=base.page_title,
                revision_id=base.revision_id,
                labeled_by=labeled_by,
                labeled_at=stamped,
                tokenizer_source=base.tokenizer_source,
                dadmatools_version=base.dadmatools_version,
                tokens_minted_at=base.tokens_minted_at,
                extra=base.extra,
            )
        )
    return out


def assign_strata_quotas(
    candidates: list[GoldExample],
    *,
    quotas: dict[str, int] | None = None,
) -> tuple[list[GoldExample], dict[str, int], dict[str, int]]:
    """Greedy fill of strata quotas without inventing sentences.

    Returns (selected, filled_counts, shortfalls).
    """
    quotas = dict(quotas or STRATA_QUOTAS)
    filled = {k: 0 for k in quotas}
    selected: list[GoldExample] = []
    used: set[str] = set()

    def need() -> list[str]:
        return [k for k, n in quotas.items() if filled[k] < n]

    # Pass 1: cover unmet strata.
    changed = True
    while changed and need():
        changed = False
        for stratum in need():
            for cand in candidates:
                if cand.id in used:
                    continue
                if stratum in cand.strata:
                    selected.append(cand)
                    used.add(cand.id)
                    for s in cand.strata:
                        if s in filled:
                            filled[s] += 1
                    changed = True
                    break

    shortfalls = {k: max(0, quotas[k] - filled[k]) for k in quotas}
    return selected, filled, shortfalls
