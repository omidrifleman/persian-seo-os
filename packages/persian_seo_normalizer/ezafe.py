"""تشخیص کسره اضافه (ezafe) — دامنه نزدیک به نمایش، جدا از analyze_form.

خروجی span است؛ متن mutate نمی‌شود. وابستگی DadmaTools فقط با import تنبل
داخل backend و فقط وقتی extras[nlp] نصب باشد.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

_UNSET = object()

_SCORE_ATTRS = ("kasreh_score", "kasreh_confidence", "score", "confidence")


@dataclass(frozen=True)
class EzafeMark:
    """یک توکن و وضعیت کسرهٔ اضافه‌اش."""

    index: int
    token: str
    has_ezafe: bool
    confidence: float  # 0.0 .. 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")


class EzafeBackendUnavailable(RuntimeError):
    """Backend تشخیص ezafe در دسترس نیست (معمولاً extras nlp نصب نشده)."""


@runtime_checkable
class EzafeBackend(Protocol):
    def detect(self, text: str) -> list[EzafeMark]: ...


def _kasreh_truthy(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text not in {"", "o", "other", "none", "null", "_", "-", "0", "false", "no"}


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


def _token_confidence(token: object) -> float:
    for attr in _SCORE_ATTRS:
        raw = _attr_or_key(token, attr)
        if isinstance(raw, (int, float)):
            return max(0.0, min(1.0, float(raw)))
    # DadmaTools kasreh is typically a hard label → full confidence in that decision.
    return 1.0


def _iter_doc_tokens(doc: object) -> list[object]:
    tokens = list(getattr(doc, "tokens", None) or [])
    if tokens:
        return tokens
    if hasattr(doc, "__iter__") and not isinstance(doc, (str, bytes)):
        try:
            return list(doc)  # type: ignore[arg-type]
        except TypeError:
            pass
    sentences = getattr(getattr(doc, "_", None), "sentences", None) or []
    out: list[object] = []
    for sent in sentences:
        out.extend(getattr(sent, "tokens", []) or [])
    return out


class DadmaEzafeBackend:
    """Adapter روی DadmaTools pipeline `tok,kasreh` با import تنبل."""

    def detect(self, text: str) -> list[EzafeMark]:
        try:
            import dadmatools.pipeline.language as language  # noqa: WPS433
        except ImportError as exc:
            raise EzafeBackendUnavailable(
                "DadmaTools is required for ezafe detection. "
                "Install optional extras: pip install 'persian-seo-os[nlp]' "
                "(dadmatools==2.3.6)."
            ) from exc

        doc = language.Pipeline("tok,kasreh")(text)
        marks: list[EzafeMark] = []
        for index, token in enumerate(_iter_doc_tokens(doc)):
            has_ezafe = _kasreh_truthy(_token_kasreh_value(token))
            marks.append(
                EzafeMark(
                    index=index,
                    token=_token_text(token),
                    has_ezafe=has_ezafe,
                    confidence=_token_confidence(token),
                )
            )
        return marks


def detect_ezafe(
    text: str,
    *,
    backend: EzafeBackend | None | object = _UNSET,
) -> list[EzafeMark]:
    """تشخیص مواضع کسره اضافه. متن را تغییر نمی‌دهد.

    backend=None → خطای روشن (تست / غیرفعال‌سازی صریح).
    بدون آرگومان → DadmaEzafeBackend (import تنبل داخل backend).
    """
    if not text or not str(text).strip():
        return []

    if backend is None:
        raise EzafeBackendUnavailable(
            "No ezafe backend configured. Install optional extras nlp "
            "(dadmatools==2.3.6) or pass an EzafeBackend."
        )

    if backend is _UNSET:
        backend = DadmaEzafeBackend()

    return backend.detect(text)  # type: ignore[union-attr]
