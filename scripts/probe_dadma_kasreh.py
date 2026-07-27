"""One-shot probe for DadmaTools kasreh — writes progress to stdout."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
CACHE = ROOT / "cache" / "dadmatools"
CACHE.mkdir(parents=True, exist_ok=True)


def main() -> int:
    t0 = time.time()
    print(f"[{time.time() - t0:.1f}s] import language", flush=True)
    import dadmatools.pipeline.language as language  # noqa: PLR0402

    print(f"[{time.time() - t0:.1f}s] create Pipeline(tok,kasreh) cache={CACHE}", flush=True)
    nlp = language.Pipeline("tok,kasreh", cache_dir=str(CACHE), gpu=False)
    print(f"[{time.time() - t0:.1f}s] pipeline ready", flush=True)

    for phrase in ("کتاب علی", "او رفت"):
        print(f"[{time.time() - t0:.1f}s] run: {phrase!r}", flush=True)
        doc = nlp(phrase)
        rows = []
        for i, tok in enumerate(doc):
            kasreh = getattr(getattr(tok, "_", None), "kasreh", None)
            rows.append({"i": i, "text": tok.text, "kasreh": kasreh})
        print(json.dumps({"phrase": phrase, "tokens": rows}, ensure_ascii=False), flush=True)

    print(f"[{time.time() - t0:.1f}s] DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
