"""Turning a finished call into its cost row: amount, rubles, payer (ADR 0035, ADR 0036)."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final

import structlog

from shosai.core.ai.calls import EFFECT_KEY_MAX_LENGTH, CallContext, ModelRef
from shosai.core.ai.costs.amounts import CostSource, cost_of
from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.costs.writer import CostWriter
from shosai.core.ai.metrics import AiMetrics
from shosai.core.ai.pricing.prices import ModelPrices
from shosai.core.ai.results import Usage
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.exchange_rates.rates import CurrencyPair, ExchangeRates, Rate
from shosai.core.kernel.ids import new_id

KOPECK: Final = Decimal("0.01")
REPORTING_PROVIDERS: Final = frozenset({"openrouter"})
log = structlog.stdlib.get_logger(__name__)


def attempt_key(effect_key: str, attempt: int) -> str:
    """The key of a failed attempt: the same for every replay of the route, within 200."""
    suffix = f":failed:{attempt}"
    if len(effect_key) + len(suffix) > EFFECT_KEY_MAX_LENGTH:
        effect_key = hashlib.sha256(effect_key.encode()).hexdigest()
    return effect_key + suffix


class CallOutcome(StrEnum):
    """How a paid call ended; a failed one is recorded when the provider charged for it."""

    OK = "ok"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class MeteredCall:
    """A call the port admitted: who it is for, which model, its kind and its prices."""

    context: CallContext
    model: ModelRef
    kind: str
    prices: ModelPrices


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """Usage of a call under its own effect key and moment, such as one minute of a session."""

    call: MeteredCall
    effect_key: str
    created_at: datetime
    usage: Usage


class CallRecorder:
    """Builds the cost rows of calls and hands them to the writer."""

    def __init__(self, writer: CostWriter, rates: ExchangeRates, metrics: AiMetrics) -> None:
        self._writer = writer
        self._rates = rates
        self._metrics = metrics

    async def record(
        self, call: MeteredCall, usage: Usage, outcome: CallOutcome = CallOutcome.OK
    ) -> None:
        """Record what the call cost, once per the context's effect key."""
        rate = await self._rate()
        usage_record = UsageRecord(call, call.context.effect_key, datetime.now(UTC), usage)
        await self._writer.record(self._entry(usage_record, outcome, rate))

    async def record_failed(self, call: MeteredCall, usage: Usage, attempt: int) -> None:
        """Record a paid failure under a key of its own, so the answer that follows on the
        route is still recorded under the context's key."""
        rate = await self._rate()
        key = attempt_key(call.context.effect_key, attempt)
        usage_record = UsageRecord(call, key, datetime.now(UTC), usage)
        await self._writer.record(self._entry(usage_record, CallOutcome.FAILED, rate))

    async def record_many(self, records: Sequence[UsageRecord]) -> None:
        """Record many usages at once, each once per its own effect key (F6-C5)."""
        if not records:
            return
        rate = await self._rate()
        await self._writer.record_many(
            [self._entry(item, CallOutcome.OK, rate) for item in records]
        )

    async def _rate(self) -> Rate | None:
        """The rate for the rubles; a row without them beats a row lost with the EU home."""
        try:
            return await self._rates.latest(CurrencyPair.USD_RUB)
        except HomeUnavailableError:
            log.warning("Курс ЦБ недоступен: строка стоимости пишется без рублей")
            return None

    def _entry(self, item: UsageRecord, outcome: CallOutcome, rate: Rate | None) -> CostEntry:
        call, usage = item.call, item.usage
        amount, source = cost_of(usage, call.prices)
        if source is CostSource.PRICED and call.model.provider.value in REPORTING_PROVIDERS:
            # Провайдер обязан был назвать стоимость; сумма по ценам — запасной путь (ADR 0035).
            self._metrics.unreported(call.kind)
        context = call.context
        scope = context.payer_scope
        return CostEntry(
            home=scope.home,
            user_id=scope.user_id,
            org_id=scope.org_id,
            cost_id=new_id(),
            created_at=item.created_at,
            effect_key=item.effect_key,
            platform_account=(context.platform_account.value if context.platform_account else None),
            provider=call.model.provider.value,
            model=call.model.model,
            kind=call.kind,
            feature=context.feature,
            call_class=context.call_class.value,
            origin=context.origin.value,
            outcome=outcome.value,
            input_tokens=usage.input_tokens,
            cached_tokens=usage.cached_tokens,
            output_tokens=usage.output_tokens,
            input_audio_tokens=usage.input_audio_tokens,
            output_audio_tokens=usage.output_audio_tokens,
            units=usage.units,
            unit=usage.unit.value if usage.unit else None,
            cost_usd=amount,
            cost_source=source.value,
            exchange_rate_used=rate.value if rate else None,
            cost_rub=(amount * rate.value).quantize(KOPECK) if rate else None,
        )
