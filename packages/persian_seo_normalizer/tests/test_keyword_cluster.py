"""تست خوشه‌بندی کلیدواژه + نیت واژگانی (قطعی، بدون شبکه)."""
from __future__ import annotations

import unittest
from itertools import permutations
from typing import cast

from packages.persian_seo_normalizer import keyword_cluster as kc
from packages.persian_seo_normalizer.fingerprint import keyword_fingerprint
from packages.persian_seo_normalizer.keyword_cluster import (
    KeywordInput,
    SearchDemandStatus,
    cluster_keywords,
    detect_search_intent,
    make_cluster_id,
)
from packages.persian_seo_normalizer.normalize import analyze_form


def _surfaces(markers: tuple) -> tuple[str, ...]:
    return tuple(m.surface for m in markers)


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


class OverlappingMarkersTest(unittest.TestCase):
    def test_gheymat_kharid_consumes_span(self) -> None:
        intent, markers, codes, competing = detect_search_intent("قیمت خرید لپ تاپ")
        self.assertEqual(intent, "transactional")
        self.assertEqual(_surfaces(markers), ("قیمت خرید",))
        self.assertNotIn("multiple_intent_categories", codes)
        self.assertEqual(competing, ())
        self.assertEqual(codes, ("intent_transactional",))

    def test_arzantarin_not_arzan(self) -> None:
        intent, markers, codes, competing = detect_search_intent("لپ تاپ ارزان‌ترین")
        self.assertEqual(intent, "commercial")
        self.assertEqual(len(markers), 1)
        self.assertEqual(analyze_form(markers[0].surface), analyze_form("ارزان‌ترین"))
        self.assertNotIn("ارزان", _surfaces(markers))
        self.assertNotIn("multiple_intent_categories", codes)
        self.assertEqual(competing, ())

    def test_real_multi_intent_still_flagged(self) -> None:
        intent, markers, codes, competing = detect_search_intent("خرید بهترین لپ تاپ")
        self.assertEqual(intent, "transactional")
        self.assertEqual(set(_surfaces(markers)), {"خرید", "بهترین"})
        self.assertIn("multiple_intent_categories", codes)
        self.assertEqual(competing, ("transactional", "commercial"))


class StrippableMarkersTest(unittest.TestCase):
    def test_tarahi_site_keeps_site_in_core(self) -> None:
        result = cluster_keywords(
            [
                KeywordInput("s", "طراحی سایت"),
                KeywordInput("a", "طراحی اپلیکیشن"),
            ]
        )
        self.assertEqual(len(result.clusters), 2)
        by_id = {
            m.keyword_id: m
            for cl in result.clusters
            for m in cl.members
        }
        self.assertIn("سایت", by_id["s"].topic_core_tokens)
        self.assertIn("اپلیکیشن", by_id["a"].topic_core_tokens)
        self.assertNotEqual(
            by_id["s"].topic_core_fingerprint,
            by_id["a"].topic_core_fingerprint,
        )
        self.assertNotEqual(by_id["s"].intent, "navigational")
        self.assertNotEqual(by_id["a"].intent, "navigational")
        self.assertEqual(by_id["s"].intent, "unknown")
        self.assertEqual(by_id["a"].intent, "unknown")

    def test_site_rasmi_irancell_is_navigational(self) -> None:
        result = cluster_keywords([KeywordInput("n", "سایت رسمی ایرانسل")])
        self.assertEqual(len(result.clusters), 1)
        rec = result.clusters[0].members[0]
        self.assertEqual(rec.intent, "navigational")
        self.assertEqual(tuple(rec.topic_core_tokens), ("ایرانسل",))
        self.assertTrue(all(m.strippable for m in rec.intent_markers))
        self.assertEqual(_surfaces(rec.intent_markers), ("سایت رسمی",))

    def test_amozesh_telegram_is_informational(self) -> None:
        result = cluster_keywords([KeywordInput("t", "آموزش تلگرام")])
        rec = result.clusters[0].members[0]
        self.assertEqual(rec.intent, "informational")
        self.assertIn("تلگرام", rec.topic_core_tokens)
        self.assertNotIn("آموزش", rec.topic_core_tokens)

    def test_forushgah_stays_in_core(self) -> None:
        result = cluster_keywords([KeywordInput("f", "فروشگاه اینترنتی")])
        rec = result.clusters[0].members[0]
        self.assertIn("فروشگاه", rec.topic_core_tokens)
        self.assertEqual(rec.intent, "commercial")

    def test_kharid_stripped_from_core(self) -> None:
        result = cluster_keywords([KeywordInput("t", "خرید لپ تاپ")])
        rec = result.clusters[0].members[0]
        self.assertNotIn("خرید", rec.topic_core_tokens)
        self.assertEqual(tuple(rec.topic_core_tokens), ("لپ", "تاپ"))
        self.assertEqual(rec.intent, "transactional")


class CatalogAndHeadTest(unittest.TestCase):
    def test_catalog_dedup_conflict_raises(self) -> None:
        specs = (
            kc._MarkerSpec("foo", "commercial", True),
            kc._MarkerSpec("foo", "transactional", True),
        )
        with self.assertRaises(ValueError) as ctx:
            kc._build_marker_catalog(specs)
        self.assertIn("conflict", str(ctx.exception))

    def test_catalog_identical_duplicate_ok(self) -> None:
        specs = (
            kc._MarkerSpec("ارزان ترین", "commercial", True),
            kc._MarkerSpec("ارزان‌ترین", "commercial", True),
        )
        catalog = kc._build_marker_catalog(specs)
        self.assertEqual(len(catalog), 1)

    def test_head_decided_by_shorter_normalized_surface(self) -> None:
        # Same demand/status; same content_tokens («را» is an SEO stopword).
        # analyze_form lengths differ → criterion 4 (shorter_normalized_surface).
        result = cluster_keywords(
            [
                KeywordInput("long", "خرید لپ تاپ را"),
                KeywordInput("short", "خرید لپ تاپ"),
            ]
        )
        self.assertEqual(len(result.clusters), 1)
        cl = result.clusters[0]
        self.assertEqual(
            {m.keyword_id for m in cl.members},
            {"long", "short"},
        )
        self.assertEqual(cl.members[0].content_tokens, cl.members[1].content_tokens)
        self.assertEqual(cl.head_keyword_id, "short")
        self.assertEqual(cl.head_decided_by, "shorter_normalized_surface")

    def test_whitespace_noise_falls_to_keyword_id_tiebreak(self) -> None:
        # Extra U+0020 is not a ranking signal after analyze_form; criteria 1–4 tie
        # → keyword_id_tiebreak picks lexicographically smaller id ("a").
        result = cluster_keywords(
            [
                KeywordInput("b", "قیمت\u0020\u0020لپ تاپ"),
                KeywordInput("a", "قیمت\u0020لپ تاپ"),
            ]
        )
        self.assertEqual(len(result.clusters), 1)
        cl = result.clusters[0]
        self.assertEqual(cl.head_keyword_id, "a")
        self.assertEqual(cl.head_decided_by, "keyword_id_tiebreak")


class IntentConflictTest(unittest.TestCase):
    def test_priority_transactional_over_commercial(self) -> None:
        intent, markers, codes, competing = detect_search_intent(
            "خرید بهترین لپ تاپ ارزان"
        )
        self.assertEqual(intent, "transactional")
        self.assertIn("خرید", _surfaces(markers))
        self.assertIn("بهترین", _surfaces(markers))
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

    def test_invalid_demand_status(self) -> None:
        item = KeywordInput(
            "z",
            "لپ تاپ ایسوس",
            search_demand_status=cast(SearchDemandStatus, "bogus"),
        )
        result = cluster_keywords([item])
        self.assertEqual(result.skipped[0].reason_code, "invalid_demand_status")

    def test_missing_search_demand(self) -> None:
        result = cluster_keywords(
            [
                KeywordInput(
                    "z",
                    "لپ تاپ ایسوس",
                    search_demand=None,
                    search_demand_status="known",
                )
            ]
        )
        self.assertEqual(result.skipped[0].reason_code, "missing_search_demand")

    def test_negative_search_demand(self) -> None:
        result = cluster_keywords(
            [
                KeywordInput(
                    "z",
                    "لپ تاپ ایسوس",
                    search_demand=-1,
                    search_demand_status="known",
                )
            ]
        )
        self.assertEqual(result.skipped[0].reason_code, "negative_search_demand")

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
    def test_deterministic_full_result_across_permutations(self) -> None:
        items = [
            KeywordInput(
                "1", "قیمت لپ تاپ", search_demand=100, search_demand_status="known"
            ),
            KeywordInput("2", "بهترین لپ تاپ"),
            KeywordInput("3", "خرید لپ تاپ"),
            KeywordInput("", "خالی"),
            KeywordInput("x", "خرید"),
        ]
        results = [cluster_keywords(list(p)) for p in permutations(items)]
        baseline = results[0]
        for r in results[1:]:
            self.assertEqual(r, baseline)

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
