"""Metrics and gold-file loading for ezafe evaluation (no model dependency)."""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GoldExample:
    id: str
    text: str
    tokens: tuple[str, ...]
    ezafe: tuple[int, ...]
    note: str = ""
    verified: bool = False

    def __post_init__(self) -> None:
        if len(self.tokens) != len(self.ezafe):
            raise ValueError(
                f"gold id={self.id!r}: len(tokens)={len(self.tokens)} != len(ezafe)={len(self.ezafe)}"
            )
        if any(v not in (0, 1) for v in self.ezafe):
            raise ValueError(f"gold id={self.id!r}: ezafe must be 0/1 only, got {self.ezafe!r}")


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


def load_ezafe_gold(path: str | Path) -> list[GoldExample]:
    """Load JSONL gold file. Missing/empty file → clear error (no fake metrics)."""
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
        examples.append(
            GoldExample(
                id=str(raw["id"]),
                text=str(raw["text"]),
                tokens=tuple(str(t) for t in raw["tokens"]),
                ezafe=tuple(int(v) for v in raw["ezafe"]),
                note=str(raw.get("note", "")),
                verified=bool(raw.get("verified", False)),
            )
        )
    if not examples:
        raise ValueError(
            f"Ezafe gold file has no examples: {p}. Refusing to print fabricated metrics."
        )
    return examples


def confusion_counts(gold: Iterable[int], pred: Iterable[int]) -> BinaryCounts:
    """Token-level binary confusion for ezafe presence (1=positive)."""
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

    lines = [
        f"examples={n_examples} tokens={n_tokens}",
        f"confusion tp={counts.tp} fp={counts.fp} tn={counts.tn} fn={counts.fn}",
        f"precision={fmt(counts.precision)} recall={fmt(counts.recall)} f1={fmt(counts.f1)}",
    ]
    return "\n".join(lines)
