# -*- coding: utf-8 -*-
"""Unit tests for declared-keyword cannibalization detection."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from persian_seo_normalizer import (  # noqa: E402
    PageTarget,
    detect_keyword_cannibalization,
    keyword_fingerprint,
)
from persian_seo_normalizer.cannibalization import SIGNIFICANT_WORD_COUNT  # noqa: E402


def _page(
    page_id: str,
    keyword: str,
    *,
    title: str = "",
    h1: str = "",
    priority: int | None = None,
    page_role: str = "other",
    word_count: int = 0,
    inbound_internal_links: int = 0,
    url: str | None = None,
) -> PageTarget:
    return PageTarget(
        page_id=page_id,
        url=url or f"https://example.com/{page_id}",
        title=title or page_id,
        h1=h1 or title or page_id,
        target_keyword=keyword,
        priority=priority,
        page_role=page_role,
        word_count=word_count,
        inbound_internal_links=inbound_internal_links,
    )


class TestCannibalization(unittest.TestCase):
    def test_buy_phone_variants_same_cluster(self):
        pages = [
            _page("a", "خرید گوشی", title="خرید گوشی ارزان", h1="خرید گوشی"),
            _page("b", "گوشی برای خرید", title="لیست گوشی", h1="گوشی"),
        ]
        result = detect_keyword_cannibalization(pages)
        self.assertEqual(len(result.clusters), 1)
        self.assertEqual(
            result.clusters[0].fingerprint,
            keyword_fingerprint("خرید گوشی"),
        )
        self.assertEqual(
            keyword_fingerprint("خرید گوشی"),
            keyword_fingerprint("گوشی برای خرید"),
        )

    def test_arabic_yeh_and_kaf_collapse_into_one_cluster(self):
        pages = [
            _page("a", "ك\u064aف چرم", title="کیف چرم", h1="کیف چرم"),
            _page("b", "کیف چرم", title="دیگر", h1="دیگر"),
        ]
        self.assertEqual(
            keyword_fingerprint("ك\u064aف چرم"),
            keyword_fingerprint("کیف چرم"),
        )
        result = detect_keyword_cannibalization(pages)
        self.assertEqual(len(result.clusters), 1)

    def test_exactly_one_keep_per_cluster(self):
        pages = [
            _page("a", "قیمت طلا", title="قیمت طلا", h1="قیمت طلا", priority=1),
            _page("b", "طلا قیمت", title="متفرقه", h1="متفرقه", priority=0),
        ]
        result = detect_keyword_cannibalization(pages)
        cluster = result.clusters[0]
        keeps = [p for p in cluster.pages if p.action == "keep"]
        self.assertEqual(len(keeps), 1)
        self.assertEqual(keeps[0].page_id, cluster.winner_page_id)

    def test_priority_override_conflicts_signals(self):
        weak_but_priority = _page(
            "weak",
            "خرید لپ تاپ",
            title="صفحه عمومی",
            h1="خانه",
            priority=100,
            page_role="other",
        )
        strong_signals = _page(
            "strong",
            "لپ تاپ خرید",
            title="خرید لپ تاپ",
            h1="خرید لپ تاپ",
            priority=1,
            page_role="pillar",
            inbound_internal_links=50,
            word_count=2000,
        )
        result = detect_keyword_cannibalization([weak_but_priority, strong_signals])
        cluster = result.clusters[0]
        self.assertEqual(cluster.winner_page_id, "weak")
        self.assertEqual(cluster.decided_by, "priority")
        self.assertIn("priority_override_conflicts_signals", cluster.reason_codes)
        self.assertIn("strong", cluster.reason_fa)

    def test_without_priority_title_h1_wins(self):
        weak = _page("w", "کفش ورزشی", title="متفرقه", h1="خانه")
        strong = _page("s", "ورزشی کفش", title="کفش ورزشی", h1="کفش ورزشی")
        result = detect_keyword_cannibalization([weak, strong])
        cluster = result.clusters[0]
        self.assertEqual(cluster.winner_page_id, "s")
        self.assertEqual(cluster.decided_by, "title_h1_match")

    def test_single_page_no_cluster(self):
        result = detect_keyword_cannibalization([_page("only", "سئو")])
        self.assertEqual(result.clusters, ())

    def test_empty_list(self):
        result = detect_keyword_cannibalization([])
        self.assertEqual(result.clusters, ())
        self.assertEqual(result.skipped_pages, ())

    def test_empty_keyword_skipped(self):
        pages = [
            _page("a", "   "),
            _page("b", "کیف", title="کیف", h1="کیف"),
        ]
        result = detect_keyword_cannibalization(pages)
        self.assertEqual(len(result.skipped_pages), 1)
        self.assertEqual(result.skipped_pages[0].reason_code, "empty_target_keyword")
        self.assertEqual(result.clusters, ())

    def test_idempotent_result(self):
        pages = [
            _page("a", "هاست لینوکس", title="هاست لینوکس", h1="هاست لینوکس"),
            _page("b", "لینوکس هاست", title="دیگر", h1="دیگر"),
        ]
        once = detect_keyword_cannibalization(pages)
        twice = detect_keyword_cannibalization(pages)
        self.assertEqual(once, twice)

    def test_three_pages_one_keep_two_losers(self):
        pages = [
            _page("keepme", "خرید دامنه", title="خرید دامنه", h1="خرید دامنه", priority=5),
            _page("low", "دامنه خرید", title="x", h1="y", word_count=50, page_role="other"),
            _page(
                "fat",
                "خرید دامنه",
                title="z",
                h1="w",
                word_count=SIGNIFICANT_WORD_COUNT + 10,
                page_role="other",
            ),
        ]
        result = detect_keyword_cannibalization(pages)
        cluster = result.clusters[0]
        by_id = {p.page_id: p for p in cluster.pages}
        self.assertEqual(by_id["keepme"].action, "keep")
        self.assertEqual(by_id["low"].action, "consolidate_into")
        self.assertEqual(by_id["low"].consolidate_target_id, "keepme")
        self.assertIn("significant_word_count_threshold", by_id["low"].reason_codes)
        self.assertEqual(by_id["fat"].action, "retarget")
        self.assertIn("significant_word_count_threshold", by_id["fat"].reason_codes)
        self.assertIsNone(by_id["fat"].consolidate_target_id)

    def test_word_count_exactly_at_threshold_is_retarget(self):
        """مرز inclusive: دقیقاً significant_word_count → retarget نه consolidate."""
        winner = _page(
            "win",
            "خرید مودم",
            title="خرید مودم",
            h1="خرید مودم",
            priority=3,
            page_role="other",
        )
        at_boundary = _page(
            "edge",
            "مودم خرید",
            title="x",
            h1="y",
            page_role="other",
            word_count=500,
        )
        below = _page(
            "thin",
            "خرید مودم",
            title="x",
            h1="y",
            page_role="other",
            word_count=499,
        )
        result = detect_keyword_cannibalization(
            [winner, at_boundary, below],
            significant_word_count=500,
        )
        by_id = {p.page_id: p for p in result.clusters[0].pages}
        self.assertEqual(by_id["edge"].action, "retarget")
        self.assertIn("significant_word_count_threshold", by_id["edge"].reason_codes)
        self.assertEqual(by_id["thin"].action, "consolidate_into")
        self.assertIn("significant_word_count_threshold", by_id["thin"].reason_codes)

    def test_custom_significant_word_count_changes_action(self):
        winner = _page("w", "a b", title="a b", h1="a b", priority=1, page_role="other")
        loser = _page("l", "b a", title="x", h1="y", page_role="other", word_count=100)
        low_threshold = detect_keyword_cannibalization(
            [winner, loser], significant_word_count=50
        )
        high_threshold = detect_keyword_cannibalization(
            [winner, loser], significant_word_count=200
        )
        self.assertEqual(
            next(p for p in low_threshold.clusters[0].pages if p.page_id == "l").action,
            "retarget",
        )
        self.assertEqual(
            next(p for p in high_threshold.clusters[0].pages if p.page_id == "l").action,
            "consolidate_into",
        )

    def test_decided_by_page_id_tiebreak_when_fully_tied(self):
        a = _page("aaa", "کیورد مشترک", title="x", h1="y", page_role="other")
        b = _page("bbb", "کیورد مشترک", title="x", h1="y", page_role="other")
        result = detect_keyword_cannibalization([a, b])
        cluster = result.clusters[0]
        self.assertEqual(cluster.decided_by, "page_id_tiebreak")
        self.assertEqual(cluster.winner_page_id, "bbb")  # lexicographic max

    def test_different_roles_get_differentiate(self):
        commercial = _page(
            "shop",
            "خرید عطر",
            title="خرید عطر",
            h1="خرید عطر",
            page_role="commercial",
            priority=2,
        )
        blog = _page(
            "blog",
            "عطر خرید",
            title="راهنما",
            h1="راهنما",
            page_role="informational",
            word_count=50,
        )
        result = detect_keyword_cannibalization([commercial, blog])
        cluster = result.clusters[0]
        loser = next(p for p in cluster.pages if p.action != "keep")
        self.assertEqual(loser.action, "differentiate")

    def test_evil_emoji_and_mixed_digits_in_fields(self):
        pages = [
            _page("a", "لپ تاپ ۱۵", title="لپ تاپ ۱۵ 💻", h1="لپ تاپ 15"),
            _page("b", "۱۵ لپ تاپ", title="دیگر", h1="دیگر"),
        ]
        result = detect_keyword_cannibalization(pages)
        self.assertEqual(len(result.clusters), 1)

    def test_no_noindex_action_in_public_api(self):
        pages = [
            _page("a", "تست", title="تست", h1="تست"),
            _page("b", "تست", title="x", h1="y"),
        ]
        result = detect_keyword_cannibalization(pages)
        actions = {p.action for c in result.clusters for p in c.pages}
        self.assertNotIn("noindex", actions)


if __name__ == "__main__":
    unittest.main()
