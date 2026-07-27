# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from persian_seo_normalizer import (  # noqa: E402
    analyze_form,
    audit_rtl_text,
    display_form,
    keyword_fingerprint,
    same_keyword,
    to_ascii_digits,
    to_persian_digits,
)

ZWNJ = "\u200c"


class TestAnalyzeForm(unittest.TestCase):
    def test_arabic_yeh_and_kaf_are_unified(self):
        self.assertEqual(analyze_form("ك\u064aف"), analyze_form("کیف"))

    def test_diacritics_and_tatweel_removed(self):
        self.assertEqual(analyze_form("سَلامـــ"), "سلام")

    def test_all_digit_systems_collapse_to_ascii(self):
        self.assertEqual(analyze_form("لپ تاپ ۱۵ اینچ"), analyze_form("لپ تاپ 15 اینچ"))
        self.assertEqual(analyze_form("لپ تاپ ١٥ اینچ"), analyze_form("لپ تاپ 15 اینچ"))

    def test_zwnj_variants_are_one_keyword(self):
        forms = ["می" + ZWNJ + "رود", "میرود", "می رود"]
        self.assertEqual(len({analyze_form(f) for f in forms}), 1)

    def test_plural_suffix_variants_collapse(self):
        self.assertEqual(analyze_form("کتاب" + ZWNJ + "ها"), analyze_form("کتاب ها"))

    def test_punctuation_and_whitespace_normalized(self):
        self.assertEqual(analyze_form("  قیمت،  طلا!  "), "قیمت طلا")

    def test_latin_is_lowercased(self):
        self.assertEqual(analyze_form("هاست Linux"), analyze_form("هاست linux"))


class TestDisplayForm(unittest.TestCase):
    def test_verb_prefix_gets_zwnj(self):
        self.assertEqual(display_form("میرود"), "می" + ZWNJ + "رود")
        self.assertEqual(display_form("می رود"), "می" + ZWNJ + "رود")

    def test_negative_verb_prefix(self):
        self.assertEqual(display_form("نمی داند"), "نمی" + ZWNJ + "داند")

    def test_plural_suffix_gets_zwnj(self):
        self.assertEqual(display_form("کتاب ها"), "کتاب" + ZWNJ + "ها")

    def test_superlative_suffix(self):
        self.assertEqual(display_form("بزرگ ترین"), "بزرگ" + ZWNJ + "ترین")

    def test_digits_become_persian(self):
        self.assertIn("۱۵", display_form("لپ تاپ 15 اینچ"))

    def test_latin_brand_preserved(self):
        self.assertIn("WordPress", display_form("افزونه WordPress برای سئو"))

    def test_arabic_chars_fixed_for_publishing(self):
        self.assertNotIn("\u064a", display_form("ك\u064aف چرم"))

    def test_latin_comma_becomes_persian(self):
        self.assertIn("\u060c", display_form("طلا, نقره"))

    def test_no_space_before_punctuation(self):
        self.assertNotIn(" \u060c", display_form("طلا , نقره"))

    def test_analyze_and_display_are_not_interchangeable(self):
        src = "میرود"
        self.assertNotEqual(analyze_form(src), display_form(src))


class TestFingerprint(unittest.TestCase):
    def test_same_keyword_across_orthographic_variants(self):
        self.assertTrue(same_keyword("ك\u064aف چرم", "کیف چرم"))

    def test_stopwords_ignored(self):
        self.assertTrue(same_keyword("قیمت طلا در تهران", "قیمت طلا تهران"))

    def test_word_order_ignored_by_default(self):
        self.assertTrue(same_keyword("قیمت لپ تاپ", "لپ تاپ قیمت"))

    def test_order_sensitive_mode(self):
        self.assertFalse(same_keyword("قیمت لپ تاپ", "لپ تاپ قیمت", order_sensitive=True))

    def test_different_keywords_differ(self):
        self.assertFalse(same_keyword("کیف چرم", "کفش چرم"))

    def test_fingerprint_is_stable_and_short(self):
        self.assertEqual(len(keyword_fingerprint("کیف چرم")), 16)


class TestEvilCases(unittest.TestCase):
    def test_emoji_survives_without_crash(self):
        self.assertTrue(display_form("سلام 👋 دنیا"))

    def test_mixed_three_digit_systems(self):
        self.assertEqual(analyze_form("۱٢3"), "123")

    def test_empty_and_whitespace(self):
        self.assertEqual(analyze_form("   "), "")
        self.assertEqual(display_form(""), "")

    def test_pure_latin_untouched_by_persian_punct_rules(self):
        self.assertEqual(display_form("gold, silver"), "gold, silver")

    def test_idempotent_display_form(self):
        once = display_form("میرود و کتاب ها")
        self.assertEqual(once, display_form(once))

    def test_idempotent_analyze_form(self):
        once = analyze_form("ك\u064aف  چرم ۱۵")
        self.assertEqual(once, analyze_form(once))

    def test_digit_roundtrip(self):
        self.assertEqual(to_ascii_digits(to_persian_digits("2026")), "2026")


class TestRtlQa(unittest.TestCase):
    def test_arabic_yeh_in_title_is_critical(self):
        codes = {f.code: f.severity for f in audit_rtl_text("خر\u064aد کیف", field="title")}
        self.assertEqual(codes.get("arabic_yeh_kaf"), "critical")

    def test_same_issue_in_body_is_not_critical(self):
        codes = {f.code: f.severity for f in audit_rtl_text("خر\u064aد کیف", field="body")}
        self.assertEqual(codes.get("arabic_yeh_kaf"), "high")

    def test_mixed_digits_detected(self):
        codes = [f.code for f in audit_rtl_text("قیمت ۱۵ و 20 درصد")]
        self.assertIn("mixed_digits", codes)

    def test_unencoded_persian_slug(self):
        codes = [f.code for f in audit_rtl_text("خرید-کیف", field="slug")]
        self.assertIn("unencoded_persian_slug", codes)

    def test_clean_persian_title_has_no_critical_findings(self):
        text = display_form("خرید کیف چرم طبیعی")
        self.assertEqual([f for f in audit_rtl_text(text, field="title") if f.severity == "critical"], [])

    def test_bidi_glue_detected(self):
        codes = [f.code for f in audit_rtl_text("افزونهWordPress")]
        self.assertIn("bidi_no_space", codes)


if __name__ == "__main__":
    unittest.main()
