"""Unit tests for ezafe gold worksheet/ingest (no network, no DadmaTools)."""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from persian_seo_normalizer.ezafe_gold import (
    GoldExample,
    align_token_char_spans,
    confusion_counts,
    evaluate_metric_splits,
    ingest_worksheet_csv,
    load_ezafe_gold,
    make_worksheet_rows,
    write_ezafe_gold,
    write_worksheet_csv,
)


def _ex(eid: str = "a", text: str = "کتاب علی بود.") -> GoldExample:
    tokens = tuple(t for t in text.replace(".", " .").split() if t)
    # ensure period is separate token if present
    if text.endswith(".") and tokens[-1] != ".":
        tokens = tuple(list(tokens) + ["."]) if not text[:-1].endswith(" ") else tokens
    # deterministic: tokenize manually for test
    if eid == "a" or text == "کتاب علی بود.":
        text = "کتاب علی بود."
        tokens = ("کتاب", "علی", "بود", ".")
    return GoldExample(
        id=eid,
        text=text,
        tokens=tokens,
        char_spans=align_token_char_spans(text, tokens),
        ezafe=None,
        verified=False,
        strata=("no_ezafe_candidate",),
        source="example.com",
        source_kind="ecommerce",
        source_url="https://example.com",
        license="test",
        collected_at="2026-01-01T00:00:00+00:00",
        tokenizer_source="test",
        dadmatools_version="test",
        tokens_minted_at="2026-01-01T00:00:00+00:00",
    )


class TestWorksheetIngest(unittest.TestCase):
    def test_worksheet_marks_non_labelable(self):
        rows = make_worksheet_rows([_ex()])
        token_rows = [r for r in rows if r["token_index"] != ""]
        by_tok = {r["token"]: r for r in token_rows}
        self.assertEqual(by_tok["کتاب"]["labelable"], "1")
        self.assertEqual(by_tok["کتاب"]["ezafe"], "")
        self.assertEqual(by_tok["."]["labelable"], "0")
        self.assertEqual(by_tok["."]["ezafe"], "-")

    def test_ingest_roundtrip_sets_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            gold_path = Path(tmp) / "g.jsonl"
            ws_path = Path(tmp) / "w.csv"
            write_ezafe_gold(gold_path, [_ex("a"), _ex("b")])
            base = {ex.id: ex for ex in load_ezafe_gold(gold_path, require_labeled=False)}
            write_worksheet_csv(ws_path, [base["a"]])
            with ws_path.open(encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
            for row in rows:
                if row["token_index"] == "":
                    continue
                if row["labelable"] == "0":
                    row["ezafe"] = "-"
                else:
                    row["ezafe"] = "1" if row["token"] == "کتاب" else "0"
            with ws_path.open("w", encoding="utf-8-sig", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)

            labeled = ingest_worksheet_csv(
                ws_path, base_examples=base, labeled_by="tester", labeled_at="T0"
            )
            self.assertEqual(len(labeled), 1)
            self.assertTrue(labeled[0].verified)
            self.assertEqual(labeled[0].ezafe, (1, 0, 0, 0))

    def test_ingest_rejects_label_on_non_labelable(self):
        with tempfile.TemporaryDirectory() as tmp:
            gold_path = Path(tmp) / "g.jsonl"
            ws_path = Path(tmp) / "w.csv"
            write_ezafe_gold(gold_path, [_ex("a")])
            base = {ex.id: ex for ex in load_ezafe_gold(gold_path, require_labeled=False)}
            write_worksheet_csv(ws_path, [base["a"]])
            with ws_path.open(encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
            for row in rows:
                if row["token_index"] == "":
                    continue
                if row["token"] == ".":
                    row["ezafe"] = "0"  # illegal
                elif row["labelable"] == "1":
                    row["ezafe"] = "0"
            with ws_path.open("w", encoding="utf-8-sig", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            with self.assertRaises(ValueError) as ctx:
                ingest_worksheet_csv(ws_path, base_examples=base, labeled_by="t")
            self.assertIn("non-labelable", str(ctx.exception))

    def test_eval_skips_non_labelable(self):
        text = "کتاب علی."
        tokens = ("کتاب", "علی", ".")
        ex = GoldExample(
            id="e",
            text=text,
            tokens=tokens,
            char_spans=align_token_char_spans(text, tokens),
            ezafe=(1, 0, 0),
            verified=True,
            source="fa.wikipedia.org",
            source_kind="wiki",
            source_url="https://fa.wikipedia.org/",
            license="test",
            collected_at="2026-01-01T00:00:00+00:00",
            tokenizer_source="test",
            dadmatools_version="test",
            tokens_minted_at="2026-01-01T00:00:00+00:00",
        )
        # pred wrongly marks "." as ezafe — must be ignored
        report = evaluate_metric_splits(
            [ex] * 20,
            predictions={ex.id: [1, 0, 1]},
        )
        # only one unique id in predictions — need unique ids
        examples = []
        preds = {}
        for i in range(20):
            e = GoldExample(
                id=f"e{i}",
                text=text,
                tokens=tokens,
                char_spans=align_token_char_spans(text, tokens),
                ezafe=(1, 0, 0),
                verified=True,
                source="fa.wikipedia.org",
                source_kind="wiki",
                source_url="https://fa.wikipedia.org/",
                license="test",
                collected_at="2026-01-01T00:00:00+00:00",
                tokenizer_source="test",
                dadmatools_version="test",
                tokens_minted_at="2026-01-01T00:00:00+00:00",
            )
            examples.append(e)
            preds[e.id] = [1, 0, 1]
        report = evaluate_metric_splits(examples, predictions=preds)
        self.assertEqual(report["n_skipped_non_labelable"], 20)
        self.assertEqual(report["n_labelable_tokens"], 40)
        self.assertEqual(report["overall"]["status"], "ok")
        self.assertAlmostEqual(report["overall"]["f1"] or 0.0, 1.0)

    def test_confusion_still_works(self):
        c = confusion_counts([1, 0], [1, 1])
        self.assertEqual(c.fp, 1)


if __name__ == "__main__":
    unittest.main()
