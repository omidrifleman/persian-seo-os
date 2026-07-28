"""Unit tests for ezafe gold metrics (no DadmaTools / no network)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from persian_seo_normalizer.ezafe_gold import (
    BinaryCounts,
    classify_alignment_mismatch,
    confusion_counts,
    format_metrics_report,
    load_ezafe_gold,
    metrics_slice_payload,
    tokens_aligned,
)


class TestEzafeGoldMetrics(unittest.TestCase):
    def test_confusion_perfect(self):
        c = confusion_counts([1, 0, 1, 0], [1, 0, 1, 0])
        self.assertEqual(c, BinaryCounts(tp=2, fp=0, tn=2, fn=0))
        self.assertEqual(c.precision, 1.0)
        self.assertEqual(c.recall, 1.0)
        self.assertEqual(c.f1, 1.0)

    def test_confusion_fp_fn(self):
        c = confusion_counts([1, 1, 0, 0], [1, 0, 1, 0])
        self.assertEqual(c.tp, 1)
        self.assertEqual(c.fn, 1)
        self.assertEqual(c.fp, 1)
        self.assertEqual(c.tn, 1)
        self.assertAlmostEqual(c.precision or 0.0, 0.5)
        self.assertAlmostEqual(c.recall or 0.0, 0.5)
        self.assertAlmostEqual(c.f1 or 0.0, 0.5)

    def test_precision_undefined_when_no_positive_preds(self):
        c = confusion_counts([1, 0], [0, 0])
        self.assertIsNone(c.precision)
        self.assertEqual(c.recall, 0.0)
        self.assertIsNone(c.f1)

    def test_load_missing_and_empty_raise(self):
        with self.assertRaises(FileNotFoundError):
            load_ezafe_gold(Path("no/such/ezafe_gold.jsonl"))
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.jsonl"
            empty.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                load_ezafe_gold(empty)
            self.assertIn("empty", str(ctx.exception).lower())

    def test_load_valid_jsonl_unlabeled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.jsonl"
            path.write_text(
                '{"id":"a","text":"کتاب علی","tokens":["کتاب","علی"],'
                '"ezafe":null,"verified":false}\n',
                encoding="utf-8",
            )
            examples = load_ezafe_gold(path, require_labeled=False)
            self.assertEqual(len(examples), 1)
            self.assertIsNone(examples[0].ezafe)
            self.assertFalse(examples[0].verified)

    def test_format_report_contains_counts(self):
        text = format_metrics_report(
            BinaryCounts(tp=1, fp=0, tn=1, fn=0), n_examples=20, n_tokens=40
        )
        self.assertIn("tp=1", text)
        self.assertIn("precision=", text)

    def test_format_report_insufficient_sample(self):
        text = format_metrics_report(
            BinaryCounts(tp=1, fp=0, tn=1, fn=0), n_examples=5, n_tokens=10
        )
        self.assertEqual(text, "insufficient_sample")

    def test_metrics_slice_payload_gates_small_n(self):
        c = BinaryCounts(tp=1, fp=0, tn=1, fn=0)
        small = metrics_slice_payload(c, n_examples=19, n_tokens=38)
        self.assertEqual(small, {"status": "insufficient_sample"})
        big = metrics_slice_payload(c, n_examples=20, n_tokens=40)
        self.assertEqual(big["status"], "ok")
        self.assertIn("f1", big)

    def test_alignment_helpers(self):
        self.assertTrue(tokens_aligned(["a", "b"], ["a", "b"]))
        self.assertFalse(tokens_aligned(["a"], ["a", "b"]))
        self.assertEqual(
            classify_alignment_mismatch(["foo."], ["foo"]),
            "punctuation",
        )
        self.assertEqual(
            classify_alignment_mismatch(["می‌رود"], ["می", "رود"]),
            "zwnj",
        )
        self.assertEqual(
            classify_alignment_mismatch(["۱۲۳"], ["12", "3"]),
            "number",
        )
        self.assertEqual(
            classify_alignment_mismatch(["iPhone"], ["i", "Phone"]),
            "latin",
        )


if __name__ == "__main__":
    unittest.main()
