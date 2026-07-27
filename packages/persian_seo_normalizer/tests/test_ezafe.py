# -*- coding: utf-8 -*-
"""TDD tests for ezafe detection — written before implementation."""
from __future__ import annotations

import importlib
import os
import sys
import unittest
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TestBasePackageImport(unittest.TestCase):
    def test_base_package_import_without_nlp_extras(self):
        """Importing the package must not require dadmatools/torch."""
        for mod in list(sys.modules):
            if mod == "persian_seo_normalizer" or mod.startswith("persian_seo_normalizer."):
                del sys.modules[mod]
        # Ensure dadmatools is not already loaded as a side-effect of this suite.
        self.assertNotIn("dadmatools", sys.modules)
        pkg = importlib.import_module("persian_seo_normalizer")
        self.assertTrue(hasattr(pkg, "detect_ezafe"))
        self.assertNotIn("dadmatools", sys.modules)
        self.assertNotIn("torch", sys.modules)


class TestEzafeApi(unittest.TestCase):
    def test_public_exports(self):
        from persian_seo_normalizer import (  # noqa: WPS433
            EzafeBackendUnavailable,
            EzafeMark,
            detect_ezafe,
        )

        self.assertTrue(callable(detect_ezafe))
        self.assertTrue(issubclass(EzafeBackendUnavailable, Exception))
        mark = EzafeMark(index=0, token="کتاب", has_ezafe=True, confidence=0.9)
        self.assertEqual(mark.confidence, 0.9)

    def test_missing_backend_raises_clear_error(self):
        from persian_seo_normalizer import EzafeBackendUnavailable, detect_ezafe

        with self.assertRaises(EzafeBackendUnavailable) as ctx:
            detect_ezafe("کتاب خوب", backend=None)
        msg = str(ctx.exception).lower()
        self.assertTrue("nlp" in msg or "dadmatools" in msg or "extras" in msg)

    def test_detect_ezafe_returns_marks_with_mock_backend(self):
        from persian_seo_normalizer import EzafeMark, detect_ezafe

        @dataclass
        class _FakeBackend:
            def detect(self, text: str) -> list[EzafeMark]:
                return [
                    EzafeMark(index=0, token="کتاب", has_ezafe=True, confidence=0.91),
                    EzafeMark(index=1, token="خوب", has_ezafe=False, confidence=0.88),
                ]

        marks = detect_ezafe("کتاب خوب", backend=_FakeBackend())
        self.assertEqual(len(marks), 2)
        self.assertEqual(marks[0].token, "کتاب")
        self.assertTrue(marks[0].has_ezafe)
        self.assertGreaterEqual(marks[0].confidence, 0.0)
        self.assertLessEqual(marks[0].confidence, 1.0)

    def test_confidence_required_on_marks(self):
        from persian_seo_normalizer import EzafeMark, detect_ezafe

        @dataclass
        class _FakeBackend:
            def detect(self, text: str) -> list[EzafeMark]:
                return [EzafeMark(index=0, token="خانه", has_ezafe=True, confidence=0.75)]

        marks = detect_ezafe("خانه بزرگ", backend=_FakeBackend())
        self.assertTrue(hasattr(marks[0], "confidence"))
        self.assertIsInstance(marks[0].confidence, float)
        self.assertGreaterEqual(marks[0].confidence, 0.0)
        self.assertLessEqual(marks[0].confidence, 1.0)

    def test_empty_and_whitespace(self):
        from persian_seo_normalizer import EzafeMark, detect_ezafe

        @dataclass
        class _FakeBackend:
            def detect(self, text: str) -> list[EzafeMark]:
                if not text.strip():
                    return []
                return [EzafeMark(index=0, token=text, has_ezafe=False, confidence=1.0)]

        backend = _FakeBackend()
        self.assertEqual(detect_ezafe("", backend=backend), [])
        self.assertEqual(detect_ezafe("   ", backend=backend), [])

    def test_emoji_and_mixed_script_do_not_crash(self):
        from persian_seo_normalizer import EzafeMark, detect_ezafe

        @dataclass
        class _FakeBackend:
            def detect(self, text: str) -> list[EzafeMark]:
                return [EzafeMark(index=0, token=text, has_ezafe=False, confidence=0.5)]

        marks = detect_ezafe("سلام WordPress 👋 دنیا", backend=_FakeBackend())
        self.assertEqual(len(marks), 1)

    def test_mark_list_idempotent_re_detect(self):
        from persian_seo_normalizer import EzafeMark, detect_ezafe

        @dataclass
        class _FakeBackend:
            def detect(self, text: str) -> list[EzafeMark]:
                return [
                    EzafeMark(index=0, token="قیمت", has_ezafe=True, confidence=0.8),
                    EzafeMark(index=1, token="طلا", has_ezafe=False, confidence=0.7),
                ]

        backend = _FakeBackend()
        text = "قیمت طلا"
        once = detect_ezafe(text, backend=backend)
        twice = detect_ezafe(text, backend=backend)
        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
