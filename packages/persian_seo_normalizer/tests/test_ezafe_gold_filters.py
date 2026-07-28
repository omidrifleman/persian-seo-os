"""Unit tests for ezafe gold body filters and labelable tokens (no network)."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from persian_seo_normalizer.ezafe_gold_filters import (
    dedupe_template_clusters,
    is_token_labelable,
    rejection_reason,
    sentence_template_fingerprint,
)


class TestBodyFilters(unittest.TestCase):
    def test_rejects_boilerplate(self):
        self.assertEqual(
            rejection_reason("ثبت نظر نظر شما با موفقیت ثبت شد."),
            "ui_chrome",
        )
        self.assertEqual(
            rejection_reason("نمایش بیشتر همه حقوق برای بازار باسلام است."),
            "ui_chrome",
        )
        self.assertEqual(
            rejection_reason("پنل فروشگاه من ثبت فروشگاه جدید پشتیبانی info@emalls.ir"),
            "email_or_url",
        )
        self.assertEqual(
            rejection_reason("۲ روز قبل تریلر فیلم جدید را ببینید اینجا."),
            "relative_time",
        )
        self.assertEqual(
            rejection_reason("| تک‌تاک کورش چایچی | هفت نکته مهم برای خرید."),
            "ellipsis_or_pipe",
        )
        self.assertEqual(
            rejection_reason("این جمله کوتاه است."),
            "too_few_persian_tokens",
        )

    def test_accepts_real_clause(self):
        s = "این محصول برای پوست خشک طراحی شده و جذب سریعی دارد."
        self.assertIsNone(rejection_reason(s))

    def test_labelable_tokens(self):
        self.assertFalse(is_token_labelable("."))
        self.assertFalse(is_token_labelable("،"))
        self.assertFalse(is_token_labelable("۱۲۳"))
        self.assertFalse(is_token_labelable("iPhone"))
        self.assertFalse(is_token_labelable("\u200c"))
        self.assertTrue(is_token_labelable("کتاب"))
        self.assertTrue(is_token_labelable("می‌رود"))

    def test_template_fingerprint_clusters_villages(self):
        a = "آبادان، روستایی از توابع بخش مرکزی شهرستان اهواز در استان خوزستان ایران است."
        b = "بروجن، روستایی از توابع بخش مرکزی شهرستان شهرکرد در استان چهارمحال ایران است."
        c = "کتابخانه ملی ایران در تهران قرار دارد و منابع بسیاری نگه می‌دارد."
        self.assertEqual(
            sentence_template_fingerprint(a),
            sentence_template_fingerprint(b),
        )
        self.assertNotEqual(
            sentence_template_fingerprint(a),
            sentence_template_fingerprint(c),
        )
        kept, report = dedupe_template_clusters([a, b, a, b, a, b, c], max_per_cluster=3)
        self.assertEqual(report.largest_cluster, 6)
        self.assertEqual(len(kept), 4)  # 3 from village cluster + 1 other
        self.assertIn(6, kept)  # index of c


if __name__ == "__main__":
    unittest.main()
