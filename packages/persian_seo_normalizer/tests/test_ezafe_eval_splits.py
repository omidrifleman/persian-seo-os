"""Unit tests for eval split reporting (no network / no DadmaTools)."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from persian_seo_normalizer.ezafe_gold import GoldExample, evaluate_metric_splits


def _ex(
    eid: str,
    *,
    source: str,
    source_kind: str,
    strata: tuple[str, ...] = (),
    ezafe: tuple[int, ...] = (0, 1),
) -> GoldExample:
    return GoldExample(
        id=eid,
        text="کتاب علی",
        tokens=("کتاب", "علی"),
        ezafe=ezafe,
        verified=True,
        strata=strata,
        source=source,
        source_kind=source_kind,
        source_url="https://example.com/",
        license="test",
        collected_at="2026-01-01T00:00:00+00:00",
    )


class TestEvalSplits(unittest.TestCase):
    def test_insufficient_when_under_20(self):
        examples = [
            _ex(
                f"w{i}",
                source="fa.wikipedia.org",
                source_kind="wikipedia",
                strata=("zwnj",),
            )
            for i in range(10)
        ]
        preds = {ex.id: list(ex.ezafe or []) for ex in examples}
        report = evaluate_metric_splits(examples, predictions=preds)
        self.assertEqual(report["overall"]["status"], "insufficient_sample")
        self.assertEqual(report["by_source"]["wikipedia"]["status"], "insufficient_sample")
        self.assertNotIn("f1", report["overall"])

    def test_ok_when_enough_examples(self):
        examples = [
            _ex(
                f"c{i}",
                source="digiato.com",
                source_kind="blog_portal",
                strata=("latin_brand",),
            )
            for i in range(20)
        ]
        preds = {ex.id: list(ex.ezafe or []) for ex in examples}
        report = evaluate_metric_splits(examples, predictions=preds)
        self.assertEqual(report["overall"]["status"], "ok")
        self.assertEqual(report["by_source"]["commercial"]["status"], "ok")
        self.assertAlmostEqual(report["overall"]["f1"] or 0.0, 1.0)


if __name__ == "__main__":
    unittest.main()
