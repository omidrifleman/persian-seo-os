"""Unit + env-gated integration tests for ezafe detection."""
from __future__ import annotations

import importlib
import os
import sys
import unittest
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def _mark(
    index: int,
    token: str,
    raw_label: str,
    *,
    confidence: float | None = None,
):
    """Build EzafeMark the way real Dadma labels look (string BIO-style, not bool)."""
    from persian_seo_normalizer.ezafe import EzafeMark, parse_kasreh_label

    has_ezafe, raw = parse_kasreh_label(raw_label)
    return EzafeMark(
        index=index,
        token=token,
        has_ezafe=has_ezafe,
        confidence=confidence,
        raw_label=raw,
    )


class TestBasePackageImport(unittest.TestCase):
    def test_base_package_import_without_nlp_extras(self):
        """Importing the package must not require dadmatools/torch."""
        for mod in list(sys.modules):
            if mod == "persian_seo_normalizer" or mod.startswith("persian_seo_normalizer."):
                del sys.modules[mod]
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
        mark = EzafeMark(
            index=0,
            token="کتاب",
            has_ezafe=True,
            confidence=None,
            raw_label="S-kasreh",
        )
        self.assertIsNone(mark.confidence)
        self.assertEqual(mark.raw_label, "S-kasreh")

    def test_missing_backend_raises_clear_error(self):
        from persian_seo_normalizer import EzafeBackendUnavailable, detect_ezafe

        with self.assertRaises(EzafeBackendUnavailable) as ctx:
            detect_ezafe("کتاب خوب", backend=None)
        msg = str(ctx.exception).lower()
        self.assertTrue("nlp" in msg or "dadmatools" in msg or "extras" in msg)

    def test_detect_ezafe_returns_marks_with_mock_backend(self):
        from persian_seo_normalizer import detect_ezafe

        @dataclass
        class _FakeBackend:
            def detect(self, text: str):
                return [
                    _mark(0, "کتاب", "S-kasreh"),
                    _mark(1, "خوب", "O"),
                ]

        marks = detect_ezafe("کتاب خوب", backend=_FakeBackend())
        self.assertEqual(len(marks), 2)
        self.assertEqual(marks[0].token, "کتاب")
        self.assertEqual(marks[0].raw_label, "S-kasreh")
        self.assertTrue(marks[0].has_ezafe)
        self.assertIsNone(marks[0].confidence)
        self.assertEqual(marks[1].raw_label, "O")
        self.assertFalse(marks[1].has_ezafe)

    def test_confidence_none_when_backend_does_not_score(self):
        """Dadma-style hard labels → confidence is None, never coerced to 1.0."""
        from persian_seo_normalizer import detect_ezafe

        @dataclass
        class _FakeBackend:
            def detect(self, text: str):
                return [_mark(0, "خانه", "S-kasreh", confidence=None)]

        marks = detect_ezafe("خانه بزرگ", backend=_FakeBackend())
        self.assertIsNone(marks[0].confidence)
        self.assertEqual(marks[0].raw_label, "S-kasreh")

    def test_empty_and_whitespace(self):
        from persian_seo_normalizer import detect_ezafe

        @dataclass
        class _FakeBackend:
            def detect(self, text: str):
                if not text.strip():
                    return []
                return [_mark(0, text, "O")]

        backend = _FakeBackend()
        self.assertEqual(detect_ezafe("", backend=backend), [])
        self.assertEqual(detect_ezafe("   ", backend=backend), [])

    def test_emoji_and_mixed_script_do_not_crash(self):
        from persian_seo_normalizer import detect_ezafe

        @dataclass
        class _FakeBackend:
            def detect(self, text: str):
                return [_mark(0, text, "O")]

        marks = detect_ezafe("سلام WordPress 👋 دنیا", backend=_FakeBackend())
        self.assertEqual(len(marks), 1)
        self.assertEqual(marks[0].raw_label, "O")

    def test_mark_list_idempotent_re_detect(self):
        from persian_seo_normalizer import detect_ezafe

        @dataclass
        class _FakeBackend:
            def detect(self, text: str):
                return [
                    _mark(0, "قیمت", "S-kasreh"),
                    _mark(1, "طلا", "O"),
                ]

        backend = _FakeBackend()
        text = "قیمت طلا"
        self.assertEqual(detect_ezafe(text, backend=backend), detect_ezafe(text, backend=backend))

    def test_unknown_non_o_label_is_positive_and_logged(self):
        from persian_seo_normalizer.ezafe import parse_kasreh_label

        with self.assertLogs("persian_seo_normalizer.ezafe", level="WARNING") as cm:
            has, raw = parse_kasreh_label("X-weird")
        self.assertTrue(has)
        self.assertEqual(raw, "X-weird")
        self.assertTrue(any("Unknown kasreh label" in line for line in cm.output))

    def test_cache_ready_requires_marker_not_filesize(self):
        import tempfile
        from pathlib import Path

        from persian_seo_normalizer.ezafe import (
            CACHE_READY_MARKER,
            EzafeCacheError,
            assert_dadma_cache_ready,
            write_dadma_cache_marker,
        )

        with tempfile.TemporaryDirectory() as tmp:
            # Directory alone is not enough — no size heuristics.
            with self.assertRaises(EzafeCacheError) as ctx:
                assert_dadma_cache_ready(tmp)
            self.assertIn(CACHE_READY_MARKER, str(ctx.exception))

            write_dadma_cache_marker(tmp)
            assert_dadma_cache_ready(tmp)
            self.assertTrue((Path(tmp) / CACHE_READY_MARKER).is_file())

    def test_adapter_shim_transfers_keys_or_raises(self):
        """Shim must move >0 embedding keys; zero transfer is a hard failure."""
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        import torch

        from persian_seo_normalizer.ezafe import (
            EzafeBackendUnavailable,
            apply_kasreh_embedding_adapter_shim,
            map_task_adapters_to_embedding,
        )

        emb_keys = [
            "xlmr.encoder.layer.0.output.layer_text_task_adapters.embedding.adapter_down.0.weight",
            "xlmr.encoder.layer.0.output.layer_text_task_adapters.embedding.adapter_up.weight",
        ]
        adapters = {
            "xlmr.encoder.layer.0.output.layer_text_task_adapters.ner.adapter_down.0.weight": torch.ones(2),
            "xlmr.encoder.layer.0.output.layer_text_task_adapters.ner.adapter_up.weight": torch.ones(2),
            "entity_label_ffn.layers.0.weight": torch.ones(2),
        }
        mapped = map_task_adapters_to_embedding(
            adapters, task_name="ner", embedding_keys=emb_keys
        )
        self.assertEqual(len(mapped), 2)

        with tempfile.TemporaryDirectory() as tmp:
            mdl = (
                Path(tmp)
                / "xlm-roberta-base"
                / "persian"
                / "persian.kasreh.mdl"
            )
            mdl.parent.mkdir(parents=True)
            torch.save({"adapters": adapters, "epoch": 1}, mdl)

            embedding = MagicMock()
            embedding.state_dict.return_value = {
                k: torch.zeros(2) for k in emb_keys
            }
            pipeline = SimpleNamespace(
                _config=SimpleNamespace(
                    active_lang="persian",
                    _cache_dir=tmp,
                    embedding_name="xlm-roberta-base",
                ),
                _embedding_layers=embedding,
                _embedding_weights={},
            )
            n = apply_kasreh_embedding_adapter_shim(pipeline)
            self.assertEqual(n, 2)
            embedding.load_state_dict.assert_called_once()
            loaded = embedding.load_state_dict.call_args[0][0]
            self.assertTrue(
                torch.equal(loaded[emb_keys[0]], torch.ones(2))
            )

            # Zero transferable keys → red.
            torch.save(
                {
                    "adapters": {
                        "entity_label_ffn.layers.0.weight": torch.ones(2),
                    },
                    "epoch": 1,
                },
                mdl,
            )
            with self.assertRaises(EzafeBackendUnavailable) as ctx:
                apply_kasreh_embedding_adapter_shim(pipeline)
            self.assertIn("no layer_text_task_adapters", str(ctx.exception).lower())

    def test_adapter_shim_rejects_ambiguous_task_names(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        import torch

        from persian_seo_normalizer.ezafe import (
            EzafeBackendUnavailable,
            apply_kasreh_embedding_adapter_shim,
            discover_adapter_task_names,
        )

        keys = [
            "xlmr.encoder.layer.0.output.layer_text_task_adapters.ner.adapter_up.weight",
            "xlmr.encoder.layer.0.output.layer_text_task_adapters.kasreh.adapter_up.weight",
        ]
        self.assertEqual(discover_adapter_task_names(keys), {"ner", "kasreh"})

        with tempfile.TemporaryDirectory() as tmp:
            mdl = (
                Path(tmp)
                / "xlm-roberta-base"
                / "persian"
                / "persian.kasreh.mdl"
            )
            mdl.parent.mkdir(parents=True)
            torch.save(
                {
                    "adapters": {k: torch.ones(2) for k in keys},
                    "epoch": 1,
                },
                mdl,
            )
            embedding = MagicMock()
            embedding.state_dict.return_value = {
                "xlmr.encoder.layer.0.output.layer_text_task_adapters.embedding.adapter_up.weight": torch.zeros(2)
            }
            pipeline = SimpleNamespace(
                _config=SimpleNamespace(
                    active_lang="persian",
                    _cache_dir=tmp,
                    embedding_name="xlm-roberta-base",
                ),
                _embedding_layers=embedding,
            )
            with self.assertRaises(EzafeBackendUnavailable) as ctx:
                apply_kasreh_embedding_adapter_shim(pipeline)
            self.assertIn("multiple task names", str(ctx.exception).lower())

    def test_audit_ezafe_skips_with_reason_when_backend_missing(self):
        from persian_seo_normalizer import EZAFE_AUDIT_CODE, audit_ezafe_kasreh

        findings = audit_ezafe_kasreh("کتاب علی", backend=None)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].skipped)
        self.assertEqual(findings[0].code, EZAFE_AUDIT_CODE)
        self.assertEqual(findings[0].severity, "low")
        self.assertTrue(findings[0].skip_reason)

    def test_audit_ezafe_emits_findings_with_raw_label(self):
        from persian_seo_normalizer import EZAFE_AUDIT_CODE, audit_ezafe_kasreh

        @dataclass
        class _FakeBackend:
            def detect(self, text: str):
                return [
                    _mark(0, "کتاب", "S-kasreh"),
                    _mark(1, "علی", "O"),
                ]

        findings = audit_ezafe_kasreh("کتاب علی", backend=_FakeBackend())
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0].skipped)
        self.assertEqual(findings[0].code, EZAFE_AUDIT_CODE)
        self.assertEqual(findings[0].severity, "low")
        self.assertEqual(findings[0].sample, "کتاب")
        self.assertEqual(findings[0].raw_label, "S-kasreh")
        self.assertIsNone(findings[0].confidence)


@unittest.skipUnless(
    os.getenv("PERSIAN_SEO_NLP_TESTS") == "1",
    "set PERSIAN_SEO_NLP_TESTS=1 to run DadmaTools integration tests",
)
class TestEzafeDadmaIntegration(unittest.TestCase):
    """Real DadmaTools backend — env-gated so the default suite stays offline/fast.

    Phrase choices:
    - WITH ezafe: «کتاب علی» — classic genitive NP; kasreh links کتاب to علی.
    - WITHOUT ezafe: «او رفت» — subject + past verb; no ezafe between them.
    """

    @classmethod
    def setUpClass(cls) -> None:
        from persian_seo_normalizer.ezafe import DadmaEzafeBackend

        DadmaEzafeBackend._pipeline = None
        DadmaEzafeBackend._pipeline_cache_dir = None
        if not os.environ.get("PERSIAN_SEO_DADMA_CACHE"):
            repo_cache = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "cache", "dadmatools")
            )
            os.environ["PERSIAN_SEO_DADMA_CACHE"] = repo_cache

    def test_phrase_with_ezafe_yields_at_least_one_positive_mark(self):
        from persian_seo_normalizer import detect_ezafe

        marks = detect_ezafe("کتاب علی")
        self.assertTrue(marks, "expected token marks from DadmaTools")
        positives = [m for m in marks if m.has_ezafe]
        self.assertGreaterEqual(
            len(positives),
            1,
            f"expected ≥1 has_ezafe=True in «کتاب علی», got {marks!r}",
        )
        self.assertTrue(any(m.raw_label and m.raw_label != "O" for m in positives))
        for m in marks:
            if m.confidence is not None:
                self.assertGreaterEqual(m.confidence, 0.0)
                self.assertLessEqual(m.confidence, 1.0)

    def test_phrase_without_ezafe_yields_no_positive_marks(self):
        from persian_seo_normalizer import detect_ezafe

        marks = detect_ezafe("او رفت")
        positives = [m for m in marks if m.has_ezafe]
        self.assertEqual(
            positives,
            [],
            f"expected no has_ezafe=True in «او رفت», got {marks!r}",
        )
        for m in marks:
            self.assertEqual(m.raw_label, "O")
            self.assertIsNone(m.confidence)


if __name__ == "__main__":
    unittest.main()
