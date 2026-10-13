"""The cost of a call: the provider's reported amount, else units times prices (ADR 0035)."""

from decimal import Decimal
from enum import StrEnum

from shosai.core.ai.pricing.prices import ModelPrices
from shosai.core.ai.results import Unit, Usage


class CostSource(StrEnum):
    """Where a row's amount came from."""

    REPORTED = "reported"
    PRICED = "priced"


def is_priced(prices: ModelPrices, alternatives: tuple[frozenset[Unit], ...]) -> bool:
    """Whether every unit of at least one way the call's kind is charged has a price in force."""
    return any(needed <= prices.keys() for needed in alternatives)


def cost_of(usage: Usage, prices: ModelPrices) -> tuple[Decimal, CostSource]:
    """The call's cost in USD and its source; reported cost wins when the provider gave one."""
    if usage.reported_cost_usd is not None:
        return usage.reported_cost_usd, CostSource.REPORTED
    # Кэшированные токены дешевле, если у модели есть их цена; иначе — по цене входных.
    cached_price = prices.get(Unit.CACHED_INPUT, prices.get(Unit.INPUT, Decimal(0)))
    fresh_input = max(usage.input_tokens - usage.cached_tokens, 0)
    total = (
        fresh_input * prices.get(Unit.INPUT, Decimal(0))
        + usage.cached_tokens * cached_price
        + usage.output_tokens * prices.get(Unit.OUTPUT, Decimal(0))
        + usage.input_audio_tokens * prices.get(Unit.INPUT_AUDIO, Decimal(0))
        + usage.output_audio_tokens * prices.get(Unit.OUTPUT_AUDIO, Decimal(0))
    )
    if usage.unit is not None:
        total += usage.units * prices.get(usage.unit, Decimal(0))
    return total, CostSource.PRICED
