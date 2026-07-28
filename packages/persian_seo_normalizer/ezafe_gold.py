"""Gold ezafe corpus helpers: schema, tokenize, load, worksheet I/O, metrics."""
from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


@dataclass(frozen=True)
class GoldExample:
    id: str
    text: str
    tokens: tuple[str, ...]
    ezafe: tuple[int, ...] | None = None
    note: str = ""
    verified: bool = False
    ambiguous: bool = False
    strata: tuple[str, ...] = ()
    source: str = ""
    source_url: str = ""
    license: str = ""
    collected_at: str = ""
    page_title: str = ""
    revision_id: str = ""
    labeled_by: str = ""
    labeled_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tokens:
            raise ValueError(f"gold id={self.id!r}: tokens must be non-empty")
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


def example_to_json(ex: GoldExample) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": ex.id,
        "text": ex.text,
        "tokens": list(ex.tokens),
        "ezafe": None if ex.ezafe is None else list(ex.ezafe),
        "note": ex.note,
        "verified": ex.verified,
        "ambiguous": ex.ambiguous,
        "strata": list(ex.strata),
        "source": ex.source,
        "source_url": ex.source_url,
        "license": ex.license,
        "collected_at": ex.collected_at,
        "page_title": ex.page_title,
        "revision_id": ex.revision_id,
        "labeled_by": ex.labeled_by,
        "labeled_at": ex.labeled_at,
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
    known = {
        "id",
        "text",
        "tokens",
        "ezafe",
        "note",
        "verified",
        "ambiguous",
        "strata",
        "source",
        "source_url",
        "license",
        "collected_at",
        "page_title",
        "revision_id",
        "labeled_by",
        "labeled_at",
    }
    extra = {k: v for k, v in raw.items() if k not in known}
    return GoldExample(
        id=str(raw["id"]),
        text=str(raw["text"]),
        tokens=tuple(str(t) for t in raw["tokens"]),
        ezafe=ezafe,
        note=str(raw.get("note", "")),
        verified=bool(raw.get("verified", False)),
        ambiguous=bool(raw.get("ambiguous", False)),
        strata=tuple(str(s) for s in raw.get("strata", []) or []),
        source=str(raw.get("source", "")),
        source_url=str(raw.get("source_url", "")),
        license=str(raw.get("license", "")),
        collected_at=str(raw.get("collected_at", "")),
        page_title=str(raw.get("page_title", "")),
        revision_id=str(raw.get("revision_id", "")),
        labeled_by=str(raw.get("labeled_by", "")),
        labeled_at=str(raw.get("labeled_at", "")),
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


WORKSHEET_FIELDS = [
    "id",
    "text",
    "token_index",
    "token",
    "ezafe",
    "ambiguous",
    "note",
    "strata",
    "source",
    "source_url",
]


def make_worksheet_rows(examples: Iterable[GoldExample]) -> list[dict[str, str]]:
    """One CSV row per token; ezafe column left blank for blind labeling."""
    rows: list[dict[str, str]] = []
    for ex in examples:
        strata = "|".join(ex.strata)
        for i, tok in enumerate(ex.tokens):
            rows.append(
                {
                    "id": ex.id,
                    "text": ex.text if i == 0 else "",
                    "token_index": str(i),
                    "token": tok,
                    "ezafe": "",  # NEVER pre-fill from a model
                    "ambiguous": "",
                    "note": ex.note if i == 0 else "",
                    "strata": strata if i == 0 else "",
                    "source": ex.source if i == 0 else "",
                    "source_url": ex.source_url if i == 0 else "",
                }
            )
    return rows


def write_worksheet_csv(path: str | Path, examples: Iterable[GoldExample]) -> int:
    """UTF-8 with BOM for Excel on Windows. Returns row count."""
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
            try:
                idx = int((row.get("token_index") or "").strip())
            except ValueError as exc:
                raise ValueError(
                    f"Worksheet line {line_no}: token_index must be int"
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
                ezafe=tuple(labels),
                note=base.note,
                verified=True,
                ambiguous=ambiguous,
                strata=base.strata,
                source=base.source,
                source_url=base.source_url,
                license=base.license,
                collected_at=base.collected_at,
                page_title=base.page_title,
                revision_id=base.revision_id,
                labeled_by=labeled_by,
                labeled_at=stamped,
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
