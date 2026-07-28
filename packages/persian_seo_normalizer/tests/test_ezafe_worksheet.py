"""Unit tests for ezafe gold worksheet/ingest (no network, no DadmaTools)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from persian_seo_normalizer.ezafe_gold import (
    GoldExample,
    confusion_counts,
    ingest_worksheet_csv,
    load_ezafe_gold,
    make_worksheet_rows,
    write_ezafe_gold,
    write_worksheet_csv,
)


def _ex(eid: str = "a") -> GoldExample:
    return GoldExample(
        id=eid,
        text="کتاب علی بود",
        tokens=("کتاب", "علی", "بود"),
        ezafe=None,
        verified=False,
        strata=("no_ezafe_candidate",),
        source="test",
        source_url="https://example.com",
        license="test",
        collected_at="2026-01-01T00:00:00+00:00",
    )


class TestWorksheetIngest(unittest.TestCase):
    def test_worksheet_leaves_ezafe_blank(self):
        rows = make_worksheet_rows([_ex()])
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["ezafe"] == "" for r in rows))
        self.assertEqual(rows[0]["token"], "کتاب")
        self.assertEqual(rows[0]["token_index"], "0")

    def test_ingest_roundtrip_sets_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            gold_path = Path(tmp) / "g.jsonl"
            ws_path = Path(tmp) / "w.csv"
            write_ezafe_gold(gold_path, [_ex("a"), _ex("b")])
            base = {ex.id: ex for ex in load_ezafe_gold(gold_path, require_labeled=False)}
            write_worksheet_csv(ws_path, [base["a"]])
            # Human fills labels.
            import csv

            with ws_path.open(encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
            for i, row in enumerate(rows):
                row["ezafe"] = "1" if i == 0 else "0"
            with ws_path.open("w", encoding="utf-8-sig", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)

            labeled = ingest_worksheet_csv(
                ws_path, base_examples=base, labeled_by="tester", labeled_at="T0"
            )
            self.assertEqual(len(labeled), 1)
            self.assertTrue(labeled[0].verified)
            self.assertEqual(labeled[0].ezafe, (1, 0, 0))
            self.assertEqual(labeled[0].labeled_by, "tester")
            self.assertEqual(labeled[0].labeled_at, "T0")

    def test_ingest_rejects_bad_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            gold_path = Path(tmp) / "g.jsonl"
            ws_path = Path(tmp) / "w.csv"
            write_ezafe_gold(gold_path, [_ex("a")])
            base = {ex.id: ex for ex in load_ezafe_gold(gold_path, require_labeled=False)}
            write_worksheet_csv(ws_path, [base["a"]])
            import csv

            with ws_path.open(encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
            rows[0]["ezafe"] = "2"
            with ws_path.open("w", encoding="utf-8-sig", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            with self.assertRaises(ValueError) as ctx:
                ingest_worksheet_csv(ws_path, base_examples=base, labeled_by="t")
            self.assertIn("0 or 1", str(ctx.exception))

    def test_load_require_labeled_fails_until_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            gold_path = Path(tmp) / "g.jsonl"
            write_ezafe_gold(gold_path, [_ex("a")])
            with self.assertRaises(ValueError):
                load_ezafe_gold(gold_path, require_labeled=True)

    def test_confusion_still_works(self):
        c = confusion_counts([1, 0], [1, 1])
        self.assertEqual(c.fp, 1)


if __name__ == "__main__":
    unittest.main()
