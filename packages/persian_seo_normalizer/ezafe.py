"""تشخیص کسره اضافه (ezafe) — دامنه نزدیک به نمایش، جدا از analyze_form.

خروجی span است؛ متن mutate نمی‌شود. وابستگی DadmaTools فقط با import تنبل
داخل backend. تشخیص ezafe سیگنال آدیت است، نه بخشی از display_form.
"""
from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .rtl_qa import RtlFinding

_UNSET = object()
_LOG = logging.getLogger(__name__)

_SCORE_ATTRS = ("kasreh_score", "kasreh_confidence", "score", "confidence")

# Outside label only. Positive inventory is NOT closed — paper says BIO,
# runtime returned S-kasreh — so any non-O string is positive.
_OUTSIDE_LABELS = {"", "o", "other", "none", "null", "_", "-", "0", "false", "no"}

# Soft set for logging only (not for gating).
_OBSERVED_POSITIVE_LABELS = {"s-kasreh", "b-kasreh", "i-kasreh", "e-kasreh"}
_logged_unknown_labels: set[str] = set()

CACHE_ENV = "PERSIAN_SEO_DADMA_CACHE"
REQUIRE_CACHE_ENV = "PERSIAN_SEO_DADMA_REQUIRE_CACHE"
# Written only after a successful Pipeline() + adapter shim — not a size guess.
# Versioned so older markers without the shim contract are treated as incomplete.
CACHE_READY_MARKER = ".persian_seo_os_dadma_pipeline_ok.v2"
CACHE_READY_MARKER_CONTENT = "pipeline_ok\nv2\n"
EZAFE_AUDIT_CODE = "fa.text.missing_ezafe_kasreh"
# Customer-facing audit stays off until ASSUMPTION-008 closes (labeled eval / authors).
EZAFE_CUSTOMER_AUDIT_ENABLED = False

# Classic genitive NP: ezafe links کتاب to علی. Process-health smoke only —
# proves the embedding adapters were remapped; does not certify every call.
# Why this phrase: short, unambiguous ezafe, used in Dadma docs/examples.
KASREH_SMOKE_PHRASE = "کتاب علی"

_ADAPTER_TASK_RE = re.compile(r"layer_text_task_adapters\.([^.]+)\.")


@dataclass(frozen=True)
class EzafeMark:
    """یک توکن و وضعیت کسرهٔ اضافه‌اش.

    confidence:
      - float در [0, 1] وقتی بک‌اند امتیاز می‌دهد
      - None وقتی بک‌اند امتیاز نمی‌دهد (مثلاً DadmaTools با برچسب سخت)
      None را هرگز ۱.۰ تفسیر نکن — نبود امتیاز ≠ قطعیت.
      kasreh یک کلاسیفایر است و اشتباه می‌کند.
    raw_label: برچسب خام بک‌اند (مثلاً \"S-kasreh\" / \"O\").
    """

    index: int
    token: str
    has_ezafe: bool
    confidence: float | None = None
    raw_label: str | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1] or None, got {self.confidence}")


class EzafeBackendUnavailable(RuntimeError):
    """Backend تشخیص ezafe در دسترس نیست (معمولاً extras nlp / کش مدل)."""


class EzafeCacheError(RuntimeError):
    """کش مدل ناقص، خراب، یا پیکربندی‌نشده است."""


@runtime_checkable
class EzafeBackend(Protocol):
    def detect(self, text: str) -> list[EzafeMark]: ...


def dadma_cache_marker_path(cache_dir: str) -> Path:
    return Path(cache_dir) / CACHE_READY_MARKER


def write_dadma_cache_marker(cache_dir: str) -> Path:
    """فقط پس از Pipeline + shim موفق فراخوانی شود (کامل بودن کش روی دیسک)."""
    root = Path(cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = dadma_cache_marker_path(cache_dir)
    path.write_text(CACHE_READY_MARKER_CONTENT, encoding="utf-8")
    return path


def resolve_dadma_cache_dir(explicit: str | None = None) -> str:
    """مسیر مطلق کش مدل‌ها — فقط از آرگومان صریح یا env، نه مسیر نسبی CWD."""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            raise EzafeCacheError(
                f"cache_dir must be absolute, got relative {explicit!r}. "
                f"Set {CACHE_ENV} or pass an absolute path."
            )
        return str(path)
    env = os.environ.get(CACHE_ENV)
    if not env:
        raise EzafeCacheError(
            f"Set {CACHE_ENV} to an absolute directory with prefetched DadmaTools "
            "models. Relative 'cache/dadmatools' is not used (breaks when CWD changes). "
            "Offline: mount a prepared cache (including readiness marker) and point "
            f"{CACHE_ENV} at it."
        )
    path = Path(env).expanduser()
    if not path.is_absolute():
        raise EzafeCacheError(
            f"{CACHE_ENV} must be an absolute path, got {env!r}."
        )
    return str(path)


def dadma_require_cache() -> bool:
    """Production must set PERSIAN_SEO_DADMA_REQUIRE_CACHE=1 (no cold download path)."""
    return os.environ.get(REQUIRE_CACHE_ENV, "").strip() == "1"


def assert_dadma_cache_ready(cache_dir: str) -> None:
    """کش معتبر = پوشه موجود + نشانگر نسخه‌دار بارگذاری موفق.

    حدس اندازه فایل نمی‌زنیم؛ دانلود ناقص نشانگر ندارد.
    این فقط کامل بودن کش روی دیسک را می‌گوید — نه صحت هر استنتاج.
    """
    root = Path(cache_dir)
    if not root.is_dir():
        raise EzafeCacheError(
            f"DadmaTools cache directory missing: {cache_dir}. "
            f"Prefetch models offline and set {CACHE_ENV}."
        )
    marker = dadma_cache_marker_path(cache_dir)
    if not marker.is_file():
        raise EzafeCacheError(
            f"DadmaTools cache has no readiness marker ({CACHE_READY_MARKER}). "
            "Treat as incomplete/corrupt. Load Pipeline once successfully to write "
            f"the marker, or mount a cache that already includes it via {CACHE_ENV}. "
            "Dropbox/HF downloads from Iran are unreliable."
        )


def discover_adapter_task_names(adapter_keys: Iterable[str]) -> set[str]:
    """نام تسک(ها) را از کلیدهای layer_text_task_adapters.<task>. استخراج می‌کند."""
    names: set[str] = set()
    for key in adapter_keys:
        match = _ADAPTER_TASK_RE.search(key)
        if match:
            names.add(match.group(1))
    return names


def map_task_adapters_to_embedding(
    adapters: dict[str, Any],
    *,
    task_name: str,
    embedding_keys: Iterable[str],
) -> dict[str, Any]:
    """کلیدهای adapters.<task> را به adapters.embedding روی انکودر نگاشت می‌کند.

    جبران جزئی ممنوع: اگر کلیدی با needle جفت شود ولی مقصد در embedding نباشد → استثنا.
    """
    emb_key_set = set(embedding_keys)
    needle = f"layer_text_task_adapters.{task_name}."
    replacement = "layer_text_task_adapters.embedding."
    mapped: dict[str, Any] = {}
    orphan_sources: list[str] = []
    n_matched = 0
    for name, value in adapters.items():
        if needle not in name:
            continue
        n_matched += 1
        target = name.replace(needle, replacement, 1)
        if target in emb_key_set:
            mapped[target] = value
        else:
            orphan_sources.append(name)
    if orphan_sources:
        sample = orphan_sources[:5]
        raise EzafeBackendUnavailable(
            "Kasreh adapter shim: partial mapping refused. "
            f"{len(orphan_sources)} key(s) matched task={task_name!r} but have no "
            f"embedding destination (matched={n_matched}, transferred={len(mapped)}). "
            f"Sample sources: {sample!r}."
        )
    _LOG.info(
        "Kasreh adapter map: task=%r matched=%d transferred=%d",
        task_name,
        n_matched,
        len(mapped),
    )
    return mapped


def apply_kasreh_embedding_adapter_shim(pipeline: Any) -> int:
    """جبران باگ DadmaTools 2.3.6: آداپتورهای kasreh هرگز روی embedding لود نمی‌شوند.

    Upstream:
      - Base_Model با add_adapter('embedding') وزن تصادفی می‌سازد.
      - _kasreh_doc با model_name='ner' صدا می‌زند و چون 'ner' در pipelines نیست
        زودبازمى‌گردد؛ حتی با نام درست، کلیدهای چک‌پوینت
        layer_text_task_adapters.ner.* با needle adapters.kasreh.adapter جفت نمی‌شوند.
    این shim فایل *.kasreh.mdl را می‌خواند، نام تسک را از کلیدها کشف می‌کند
    (هاردکد نیست)، و به layer_text_task_adapters.embedding.* کپی می‌کند.

    Returns:
        تعداد کلیدهای منتقل‌شده به embedding (باید > 0).
    """
    try:
        import torch
    except ImportError as exc:
        raise EzafeBackendUnavailable(
            "torch is required to apply the kasreh embedding adapter shim."
        ) from exc

    lang = pipeline._config.active_lang
    cache_dir = pipeline._config._cache_dir
    embedding_name = pipeline._config.embedding_name
    mdl_path = Path(cache_dir) / embedding_name / lang / f"{lang}.kasreh.mdl"
    if not mdl_path.is_file():
        raise EzafeBackendUnavailable(
            f"Kasreh checkpoint missing for adapter shim: {mdl_path}"
        )

    checkpoint = torch.load(str(mdl_path), map_location="cpu")
    if not isinstance(checkpoint, dict) or "adapters" not in checkpoint:
        raise EzafeBackendUnavailable(
            f"Kasreh checkpoint has no 'adapters' dict: {mdl_path}"
        )
    adapters = checkpoint["adapters"]
    if not isinstance(adapters, dict) or not adapters:
        raise EzafeBackendUnavailable(
            f"Kasreh checkpoint adapters empty: {mdl_path}"
        )

    task_names = discover_adapter_task_names(adapters.keys())
    if not task_names:
        raise EzafeBackendUnavailable(
            "Kasreh checkpoint adapters contain no layer_text_task_adapters.<task> keys; "
            "cannot discover task name for embedding shim."
        )
    if len(task_names) != 1:
        raise EzafeBackendUnavailable(
            "Kasreh checkpoint adapters contain multiple task names "
            f"{sorted(task_names)!r}; refusing ambiguous embedding shim."
        )
    task_name = next(iter(task_names))

    embedding = pipeline._embedding_layers
    full_state = embedding.state_dict()
    mapped = map_task_adapters_to_embedding(
        adapters, task_name=task_name, embedding_keys=full_state.keys()
    )
    if not mapped:
        raise EzafeBackendUnavailable(
            "Kasreh embedding adapter shim transferred 0 keys "
            f"(task={task_name!r}, checkpoint={mdl_path}). "
            "Upstream adapter load is broken and shim could not compensate."
        )

    full_state.update(mapped)
    embedding.load_state_dict(full_state)
    if hasattr(pipeline, "_embedding_weights"):
        pipeline._embedding_weights = embedding.state_dict()

    _LOG.info(
        "Applied kasreh embedding adapter shim: task=%r transferred=%d path=%s",
        task_name,
        len(mapped),
        mdl_path,
    )
    return len(mapped)


def _smoke_kasreh_pipeline(pipeline: Any) -> None:
    """سلامت پروسه پس از shim — نتیجه روی دیسک ذخیره نمی‌شود.

    فقط smoke است؛ صحت هر فراخوانی بعدی را تضمین نمی‌کند.
    """
    doc = pipeline(KASREH_SMOKE_PHRASE)
    marks: list[tuple[str, object]] = []
    for token in _iter_doc_tokens(doc):
        marks.append((_token_text(token), _token_kasreh_value(token)))
    positives = [
        (text, raw)
        for text, raw in marks
        if parse_kasreh_label(raw)[0]
    ]
    if not positives:
        raise EzafeBackendUnavailable(
            "Kasreh process-health smoke failed on "
            f"{KASREH_SMOKE_PHRASE!r}: expected ≥1 ezafe mark, got {marks!r}. "
            "Embedding adapters are still random or shim did not apply."
        )


def _normalize_label(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "S-kasreh" if value else "O"
    if isinstance(value, (int, float)):
        return "S-kasreh" if value != 0 else "O"
    text = str(value).strip()
    return text if text else None


def parse_kasreh_label(value: object) -> tuple[bool, str | None]:
    """برچسب خام → (has_ezafe, raw_label).

    قاعده: هر برچسبی که O (outside) نیست مثبت است.
    فهرست مثبت‌ها بسته نیست؛ برچسب ناشناخته با logging.warning لاگ می‌شود.
    """
    raw = _normalize_label(value)
    if raw is None:
        return False, None
    lowered = raw.lower()
    if lowered in _OUTSIDE_LABELS or lowered.startswith("o-"):
        return False, raw
    if lowered not in _OBSERVED_POSITIVE_LABELS and lowered not in _logged_unknown_labels:
        _logged_unknown_labels.add(lowered)
        _LOG.warning(
            "Unknown kasreh label %r treated as has_ezafe=True "
            "(label inventory is open; paper BIO vs runtime S-kasreh).",
            raw,
        )
    return True, raw


def _attr_or_key(obj: object, name: str) -> object:
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, dict):
        return obj.get(name)
    return None


def _token_text(token: object) -> str:
    for attr in ("text", "word", "form"):
        val = _attr_or_key(token, attr)
        if isinstance(val, str):
            return val
    return str(token)


def _token_kasreh_value(token: object) -> object:
    val = _attr_or_key(token, "kasreh")
    if val is not None:
        return val
    underscore = getattr(token, "_", None)
    if underscore is not None:
        return getattr(underscore, "kasreh", None)
    return None


def _token_confidence(token: object) -> float | None:
    """None وقتی بک‌اند امتیاز نمی‌دهد — هرگز به ۱.۰ تبدیل نکن."""
    for attr in _SCORE_ATTRS:
        raw = _attr_or_key(token, attr)
        if isinstance(raw, (int, float)):
            return max(0.0, min(1.0, float(raw)))
    return None


def _iter_doc_tokens(doc: object) -> list[object]:
    if hasattr(doc, "__iter__") and not isinstance(doc, (str, bytes, dict)):
        try:
            tokens = list(doc)  # type: ignore[arg-type]
            if tokens and not isinstance(tokens[0], (str, bytes)):
                return tokens
        except TypeError:
            pass
    raw = getattr(doc, "tokens", None)
    if raw:
        return list(raw)
    sentences = getattr(getattr(doc, "_", None), "sentences", None) or []
    out: list[object] = []
    for sent in sentences:
        out.extend(getattr(sent, "tokens", []) or [])
    return out


class DadmaEzafeBackend:
    """Adapter روی DadmaTools pipeline `tok,kasreh` با import تنبل."""

    _pipeline: Any = None
    _pipeline_cache_dir: str | None = None

    def __init__(self, *, cache_dir: str | None = None, gpu: bool = False) -> None:
        self._cache_dir = cache_dir
        self._gpu = gpu

    def _get_pipeline(self) -> Any:
        cache = resolve_dadma_cache_dir(self._cache_dir)
        if (
            DadmaEzafeBackend._pipeline is not None
            and DadmaEzafeBackend._pipeline_cache_dir == cache
        ):
            return DadmaEzafeBackend._pipeline

        if dadma_require_cache():
            # Production: never attempt cold download / bootstrap without marker.
            assert_dadma_cache_ready(cache)
        else:
            _LOG.warning(
                "Cold bootstrap path: %s is not set to '1'. "
                "Skipping cache readiness assert before Pipeline(). "
                "Production deployments must set %s=1 and mount a prepared cache "
                "with %s.",
                REQUIRE_CACHE_ENV,
                REQUIRE_CACHE_ENV,
                CACHE_READY_MARKER,
            )

        try:
            # Prefer submodule import — project convention (same object as
            # `from dadmatools.pipeline import language`).
            import dadmatools.pipeline.language as language  # noqa: WPS433, PLR0402
        except ImportError as exc:
            raise EzafeBackendUnavailable(
                "DadmaTools is required for ezafe detection. "
                "Install optional extras: pip install 'persian-seo-os[nlp]' "
                "(dadmatools[full]==2.3.6)."
            ) from exc

        # Only a successful Pipeline()+shim+smoke writes the readiness marker.
        pipeline = language.Pipeline("tok,kasreh", cache_dir=cache, gpu=self._gpu)
        apply_kasreh_embedding_adapter_shim(pipeline)
        _smoke_kasreh_pipeline(pipeline)

        write_dadma_cache_marker(cache)
        assert_dadma_cache_ready(cache)
        DadmaEzafeBackend._pipeline = pipeline
        DadmaEzafeBackend._pipeline_cache_dir = cache
        return DadmaEzafeBackend._pipeline

    def detect(self, text: str) -> list[EzafeMark]:
        try:
            doc = self._get_pipeline()(text)
        except ImportError as exc:
            raise EzafeBackendUnavailable(
                "DadmaTools runtime deps missing (often dadmatools[full]). "
                "Install optional extras: pip install 'persian-seo-os[nlp]'."
            ) from exc

        marks: list[EzafeMark] = []
        for index, token in enumerate(_iter_doc_tokens(doc)):
            has_ezafe, raw_label = parse_kasreh_label(_token_kasreh_value(token))
            marks.append(
                EzafeMark(
                    index=index,
                    token=_token_text(token),
                    has_ezafe=has_ezafe,
                    confidence=_token_confidence(token),
                    raw_label=raw_label,
                )
            )
        return marks


def detect_ezafe(
    text: str,
    *,
    backend: EzafeBackend | None | object = _UNSET,
) -> list[EzafeMark]:
    """تشخیص مواضع کسره اضافه. متن را تغییر نمی‌دهد.

    بخشی از display_form نیست — فقط برای آدیت/استراتژی فراخوانی شود.
    """
    if not text or not str(text).strip():
        return []

    if backend is None:
        raise EzafeBackendUnavailable(
            "No ezafe backend configured. Install optional extras nlp "
            "(dadmatools[full]==2.3.6) or pass an EzafeBackend."
        )

    if backend is _UNSET:
        backend = DadmaEzafeBackend(gpu=False)

    return backend.detect(text)  # type: ignore[union-attr]


def audit_ezafe_kasreh(
    text: str,
    *,
    backend: EzafeBackend | None | object = _UNSET,
    field: str = "body",
    force: bool = False,
) -> list[RtlFinding]:
    """چک آدیت اختیاری کسره اضافه — فقط مسیر آدیت، نه display_form.

    کد: fa.text.missing_ezafe_kasreh، شدت low.
    اگر بک‌اند در دسترس نباشد: یک یافتهٔ skipped با دلیل روشن
    (نه raise، نه لیست خالیِ خاموش).
    یافته‌های واقعی raw_label و confidence را حمل می‌کنند.

    قرارداد گِیت کیفیت (مصرف‌کننده هنوز نوشته نشده): سه حالت جدا —
      pass = چک اجرا شد، ایرادی نیست؛
      ایراد = RtlFinding با skipped=False؛
      نامعلوم = RtlFinding با skipped=True.
    skipped=True هرگز معادل pass نیست و نباید در quality gate سبز شود.

    تا بسته شدن ASSUMPTION-008 این چک در گزارش مشتری‌رو فعال نیست
    (EZAFE_CUSTOMER_AUDIT_ENABLED=False). برای تست واحد force=True بده.
    """
    del field  # reserved for parity with audit_rtl_text callers
    if not text or not str(text).strip():
        return []

    if not force and not EZAFE_CUSTOMER_AUDIT_ENABLED:
        return [
            RtlFinding(
                code=EZAFE_AUDIT_CODE,
                severity="low",
                message="Ezafe/kasreh customer audit disabled pending ASSUMPTION-008.",
                skipped=True,
                skip_reason=(
                    "ASSUMPTION-008 open: kasreh checkpoint adapters are named 'ner'; "
                    "accuracy on labeled data is unverified. "
                    "fa.text.missing_ezafe_kasreh must not appear in customer reports."
                ),
            )
        ]

    try:
        marks = detect_ezafe(text, backend=backend)
    except (EzafeBackendUnavailable, EzafeCacheError) as exc:
        return [
            RtlFinding(
                code=EZAFE_AUDIT_CODE,
                severity="low",
                message="Ezafe/kasreh audit check skipped — backend or cache unavailable.",
                skipped=True,
                skip_reason=str(exc),
            )
        ]

    findings: list[RtlFinding] = []
    for mark in marks:
        if not mark.has_ezafe:
            continue
        # Orthography usually omits kasreh; surface the invisible ezafe link for review.
        findings.append(
            RtlFinding(
                code=EZAFE_AUDIT_CODE,
                severity="low",
                message=(
                    "رابطهٔ کسره اضافه در متن تشخیص داده شد ولی در خط نوشته نشده؛ "
                    "معنای عبارت کلیدی را عوض می‌کند — بازبینی انسانی."
                ),
                sample=mark.token,
                raw_label=mark.raw_label,
                confidence=mark.confidence,
            )
        )
    return findings
