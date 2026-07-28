"""تست خوشه‌بندی کلیدواژه + نیت واژگانی (قطعی، بدون شبکه)."""
from __future__ import annotations

import unittest

from packages.persian_seo_normalizer.fingerprint import keyword_fingerprint
from packages.persian_seo_normalizer.keyword_cluster import (
    KeywordInput,
    cluster_keywords,
    detect_search_intent,
    make_cluster_id,
)


class ReferenceLaptopClustersTest(unittest.TestCase):
    def test_four_clusters_by_topic_core_and_intent(self) -> None:
        result = cluster_keywords(
            [
                KeywordInput("t1", "خرید لپ تاپ"),
                KeywordInput("t2", "لپ تاپ برای خرید"),
                KeywordInput("c1", "قیمت لپ تاپ"),
                KeywordInput("c2", "بهترین لپ تاپ"),
                KeywordInput("c3", "لپ تاپ ارزان"),
                KeywordInput("u1", "لپ تاپ ایسوس"),
                KeywordInput("i1", "لپ تاپ چیست"),
            ]
        )
        self.assertEqual(len(result.skipped), 0)
        self.assertEqual(len(result.clusters), 4)

        by_intent = {cl.intent: cl for cl in result.clusters}
        self.assertEqual(
            {m.keyword_id for m in by_intent["transactional"].members},
            {"t1", "t2"},
        )
        self.assertEqual(
            {m.keyword_id for m in by_intent["commercial"].members},
            {"c1", "c2", "c3"},
        )
        self.assertEqual(
            {m.keyword_id for m in by_intent["unknown"].members},
            {"u1"},
        )
        self.assertEqual(
            {m.keyword_id for m in by_intent["informational"].members},
            {"i1"},
        )

        laptop_core = keyword_fingerprint("لپ تاپ")
        self.assertEqual(
            by_intent["transactional"].topic_core_fingerprint, laptop_core
        )
        self.assertEqual(by_intent["commercial"].topic_core_fingerprint, laptop_core)
        self.assertEqual(
            by_intent["informational"].topic_core_fingerprint, laptop_core
        )
        self.assertNotEqual(
            by_intent["unknown"].topic_core_fingerprint, laptop_core
        )
        self.assertEqual(
            by_intent["transactional"].cluster_id,
            make_cluster_id(laptop_core, "transactional"),
        )


class IntentConflictTest(unittest.TestCase):
    def test_priority_transactional_over_commercial(self) -> None:
        intent, markers, codes, competing = detect_search_intent(
            "خرید بهترین لپ تاپ ارزان"
        )
        self.assertEqual(intent, "transactional")
        self.assertIn("خرید", markers)
        self.assertIn("بهترین", markers)
        self.assertIn("multiple_intent_categories", codes)
        self.assertEqual(competing[0], "transactional")
        self.assertIn("commercial", competing)
        self.assertIn("intent_transactional", codes)
        self.assertIn("intent_commercial", codes)

    def test_latin_single_token_unknown(self) -> None:
        intent, markers, codes, competing = detect_search_intent("laptop")
        self.assertEqual(intent, "unknown")
        self.assertEqual(markers, ())
        self.assertEqual(codes, ("intent_unknown",))
        self.assertEqual(competing, ())


class SkipAndDemandTest(unittest.TestCase):
    def test_only_intent_markers_skipped(self) -> None:
        result = cluster_keywords([KeywordInput("x", "خرید")])
        self.assertEqual(len(result.clusters), 0)
        self.assertEqual(result.skipped[0].reason_code, "only_intent_markers")

    def test_duplicate_keyword_id_keeps_first(self) -> None:
        result = cluster_keywords(
            [
                KeywordInput("a", "خرید لپ تاپ"),
                KeywordInput("a", "قیمت لپ تاپ"),
            ]
        )
        self.assertEqual(len(result.clusters), 1)
        self.assertEqual(result.clusters[0].intent, "transactional")
        self.assertEqual(result.skipped[0].reason_code, "duplicate_keyword_id")

    def test_empty_keyword_id_separate_reason(self) -> None:
        result = cluster_keywords([KeywordInput("", "خرید لپ تاپ")])
        self.assertEqual(result.skipped[0].reason_code, "empty_keyword_id")

    def test_search_demand_zero_known_is_valid(self) -> None:
        result = cluster_keywords(
            [
                KeywordInput(
                    "z",
                    "لپ تاپ ایسوس",
                    search_demand=0,
                    search_demand_status="known",
                )
            ]
        )
        self.assertEqual(len(result.skipped), 0)
        self.assertEqual(len(result.clusters), 1)
        rec = result.clusters[0].members[0]
        self.assertEqual(rec.search_demand, 0)
        self.assertEqual(rec.search_demand_status, "known")

    def test_unknown_with_numeric_demand_conflict(self) -> None:
        result = cluster_keywords(
            [
                KeywordInput(
                    "z",
                    "لپ تاپ ایسوس",
                    search_demand=10,
                    search_demand_status="unknown",
                )
            ]
        )
        self.assertEqual(result.skipped[0].reason_code, "demand_status_conflict")

    def test_head_prefers_known_demand_zero_over_unknown(self) -> None:
        result = cluster_keywords(
            [
                KeywordInput("u", "قیمت لپ تاپ"),
                KeywordInput(
                    "k",
                    "لپ تاپ قیمت",
                    search_demand=0,
                    search_demand_status="known",
                ),
            ]
        )
        self.assertEqual(len(result.clusters), 1)
        cl = result.clusters[0]
        self.assertEqual(cl.head_keyword_id, "k")
        self.assertEqual(cl.head_decided_by, "search_demand_status")
        self.assertEqual(cl.members[0].search_demand, 0)


class DeterminismAndFingerprintReuseTest(unittest.TestCase):
    def test_deterministic(self) -> None:
        items = [
            KeywordInput("1", "قیمت لپ تاپ", search_demand=100, search_demand_status="known"),
            KeywordInput("2", "بهترین لپ تاپ"),
            KeywordInput("3", "خرید لپ تاپ"),
        ]
        a = cluster_keywords(items)
        b = cluster_keywords(list(reversed(items)))
        self.assertEqual(
            {(c.cluster_id, c.head_keyword_id) for c in a.clusters},
            {(c.cluster_id, c.head_keyword_id) for c in b.clusters},
        )

    def test_topic_core_uses_keyword_fingerprint(self) -> None:
        result = cluster_keywords([KeywordInput("1", "قیمت لپ تاپ")])
        rec = result.clusters[0].members[0]
        self.assertEqual(
            rec.topic_core_fingerprint,
            keyword_fingerprint(" ".join(rec.topic_core_tokens)),
        )
        self.assertEqual(tuple(rec.topic_core_tokens), ("لپ", "تاپ"))

    def test_default_order_sensitive_false(self) -> None:
        result = cluster_keywords(
            [
                KeywordInput("a", "لپ تاپ قیمت"),
                KeywordInput("b", "قیمت لپ تاپ"),
            ]
        )
        self.assertEqual(len(result.clusters), 1)
        self.assertEqual(result.clusters[0].intent, "commercial")


if __name__ == "__main__":
    unittest.main()
