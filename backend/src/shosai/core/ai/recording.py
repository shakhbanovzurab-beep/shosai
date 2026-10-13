"""Turning a finished call into its cost row: amount, rubles, payer (ADR 0035, ADR 0036)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

from shosai.core.ai.calls import CallContext, ModelRef
from shosai.core.ai.costs.amounts import CostSource, cost_of
from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.costs.writer import CostWriter
from shosai.core.ai.metrics import AiMetrics
from shosai.core.ai.pricing.prices import ModelPrices
from shosai.core.ai.results import Usage
from shosai.core.exchange_rates.rates import CurrencyPair, ExchangeRates
from shosai.core.kernel.ids import new_id

KOPECK: Final = Decimal("0.01")
REPORTING_PROVIDERS: Final = frozenset({"openrouter"})


class CallRecorder:
    """Builds the cost row of a call and hands it to the writer."""

    def __init__(self, writer: CostWriter, rates: ExchangeRates, metrics: AiMetrics) -> None:
        self._writer = writer
        self._rates = rates
        self._metrics = metrics

    async def record(
        self,
        context: CallContext,
        model: ModelRef,
        kind: str,
        usage: Usage,
        prices: ModelPrices,
    ) -> None:
        """Record what the call cost, once per the context's effect key."""
        amount, source = cost_of(usage, prices)
        if source is CostSource.PRICED and model.provider.value in REPORTING_PROVIDERS:
            # Провайдер обязан был назвать стоимость; сумма по ценам — запасной путь (ADR 0035).
            self._metrics.unreported(kind)
        rate = await self._rates.latest(CurrencyPair.USD_RUB)
        scope = context.payer_scope
        entry = CostEntry(
            home=scope.home,
            user_id=scope.user_id,
            org_id=scope.org_id,
            cost_id=new_id(),
            created_at=datetime.now(UTC),
            effect_key=context.effect_key,
            platform_account=(context.platform_account.value if context.platform_account else None),
            provider=model.provider.value,
            model=model.model,
            kind=kind,
            feature=context.feature,
            call_class=context.call_class.value,
            origin=context.origin.value,
            outcome="ok",
            input_tokens=usage.input_tokens,
            cached_tokens=usage.cached_tokens,
            output_tokens=usage.output_tokens,
            units=usage.units,
            unit=usage.unit.value if usage.unit else None,
            cost_usd=amount,
            cost_source=source.value,
            exchange_rate_used=rate.value if rate else None,
            cost_rub=(amount * rate.value).quantize(KOPECK) if rate else None,
        )
        await self._writer.record(entry)
