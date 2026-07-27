"""Prefetch DadmaTools models with retries, then run a kasreh smoke probe."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
CACHE = ROOT / "cache" / "dadmatools"
PERSIAN = CACHE / "xlm-roberta-base" / "persian"


def retry(label: str, fn, attempts: int = 6):
    last = None
    for i in range(1, attempts + 1):
        try:
            print(f"[{label}] attempt {i}/{attempts}", flush=True)
            return fn()
        except Exception as exc:  # noqa: BLE001 — network flakiness
            last = exc
            print(f"[{label}] fail: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(min(30, 2 * i))
    raise RuntimeError(f"{label} failed after {attempts} attempts") from last


def prefetch() -> None:
    from huggingface_hub import hf_hub_download
    from transformers import XLMRobertaModel, XLMRobertaTokenizer

    PERSIAN.mkdir(parents=True, exist_ok=True)
    files = [
        ("Dadmatech/Vocab", "persian.vocabs.json"),
        ("Dadmatech/Lemmatizer", "persian_lemmatizer.pt"),
        ("Dadmatech/mwt_expander", "persian_mwt_expander.pt"),
        ("Dadmatech/POS", "persian.tagger.mdl"),
        ("Dadmatech/tokenizer", "persian.tokenizer.mdl"),
        ("Dadmatech/Kasreh_ezafe", "persian.kasreh.mdl"),
        ("Dadmatech/Kasreh_ezafe", "persian.kasreh-vocab.json"),
    ]
    for repo, name in files:
        retry(
            f"hf:{repo}/{name}",
            lambda r=repo, n=name: hf_hub_download(repo_id=r, filename=n, local_dir=str(PERSIAN)),
        )

    emb_cache = str(CACHE / "xlm-roberta-base")
    retry(
        "xlm-roberta-tokenizer",
        lambda: XLMRobertaTokenizer.from_pretrained("xlm-roberta-base", cache_dir=emb_cache),
    )
    retry(
        "xlm-roberta-model",
        lambda: XLMRobertaModel.from_pretrained("xlm-roberta-base", cache_dir=emb_cache),
    )


def probe() -> None:
    import dadmatools.pipeline.language as language  # noqa: PLR0402

    out_path = ROOT / "cache" / "kasreh_probe_result.jsonl"
    print("create Pipeline...", flush=True)
    nlp = language.Pipeline("tok,kasreh", cache_dir=str(CACHE), gpu=False)
    print("pipeline ready", flush=True)
    lines: list[str] = []
    for phrase in ("کتاب علی", "او رفت"):
        doc = nlp(phrase)
        rows = []
        for i, tok in enumerate(doc):
            rows.append(
                {
                    "i": i,
                    "text": tok.text,
                    "kasreh": getattr(getattr(tok, "_", None), "kasreh", None),
                }
            )
        lines.append(json.dumps({"phrase": phrase, "tokens": rows}, ensure_ascii=False))

    from persian_seo_normalizer.ezafe import DadmaEzafeBackend, detect_ezafe

    DadmaEzafeBackend._pipeline = nlp  # reuse loaded pipeline
    for phrase in ("کتاب علی", "او رفت"):
        marks = detect_ezafe(phrase, backend=DadmaEzafeBackend(cache_dir=str(CACHE), gpu=False))
        lines.append(
            json.dumps(
                {
                    "wrapper": phrase,
                    "marks": [
                        {
                            "index": m.index,
                            "token": m.token,
                            "has_ezafe": m.has_ezafe,
                            "confidence": m.confidence,
                        }
                        for m in marks
                    ],
                },
                ensure_ascii=False,
            )
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path}", flush=True)
    for line in lines:
        # ASCII-safe summary for Windows consoles
        data = json.loads(line)
        key = "wrapper" if "wrapper" in data else "phrase"
        if "tokens" in data:
            summary = [(t["text"], t["kasreh"]) for t in data["tokens"]]
        else:
            summary = [(m["token"], m["has_ezafe"], m["confidence"]) for m in data["marks"]]
        print(f"{key} ok marks/tokens={len(summary)} sample={summary!r}", flush=True)


def main() -> int:
    t0 = time.time()
    print(f"cache={CACHE}", flush=True)
    prefetch()
    print(f"prefetch done in {time.time() - t0:.1f}s", flush=True)
    probe()
    print(f"ALL DONE in {time.time() - t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
