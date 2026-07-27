"""دروازه واحد LLM.

هیچ کد بیزنسی مجاز نیست SDK یک provider را مستقیم صدا بزند.
دلایل: fallback در برابر تحریم/قطعی، کنترل بودجه ارزی، شمارش توکن، تعویض مدل بدون تغییر کد.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol


class ProviderError(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


class Provider(Protocol):
    name: str

    def complete(self, prompt: str, *, model: str, max_tokens: int) -> "Completion": ...


@dataclass
class Completion:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    fallback_from: str | None = None


@dataclass
class BudgetGuard:
    monthly_limit_usd: float
    spent_usd: float = 0.0

    def check(self, projected_usd: float) -> None:
        if self.spent_usd + projected_usd > self.monthly_limit_usd:
            raise BudgetExceeded(
                f"سقف بودجه ماهانه ({self.monthly_limit_usd}$) رد می‌شود."
            )

    def record(self, cost_usd: float) -> None:
        self.spent_usd += cost_usd


@dataclass
class LlmGateway:
    """routing + fallback زنجیره‌ای + سقف بودجه + لاگ.

    نکته فارسی: انتخاب مدل را با بنچمارک فارسی (Khayyam/PersianMMLU، MIZAN) توجیه کن،
    نه لیدربورد انگلیسی. نسبت توکن به کاراکتر فارسی مستقیماً هزینه است.
    """

    providers: list[Provider]
    budget: BudgetGuard
    on_call: Callable[[Completion], None] | None = None
    _errors: list[str] = field(default_factory=list)

    def complete(self, prompt: str, *, model: str, max_tokens: int = 2048) -> Completion:
        self.budget.check(projected_usd=0.0)
        first = self.providers[0].name if self.providers else None
        for index, provider in enumerate(self.providers):
            try:
                result = provider.complete(prompt, model=model, max_tokens=max_tokens)
            except ProviderError as exc:
                self._errors.append(f"{provider.name}: {exc}")
                continue
            if index > 0:
                result.fallback_from = first
            self.budget.record(result.cost_usd)
            if self.on_call:
                self.on_call(result)
            return result
        raise ProviderError("همه providerها ناموفق بودند: " + "; ".join(self._errors))
