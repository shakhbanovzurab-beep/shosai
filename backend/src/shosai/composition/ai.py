"""The AI provider port and the exchange rates of a process, built once and closed at stop.

The OpenRouter client exists only with its key: without it the provider is disabled and every
call is refused (`model_unavailable`); the gate requires the key outside development. A
second HTTP client serves core's own outbound calls, such as the Central Bank's rates.
"""

from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Final

import httpx
from prometheus_client import CollectorRegistry

from shosai.core.ai.adapters.openrouter import OpenRouter, openrouter_client
from shosai.core.ai.costs.settlement import CostSettlements
from shosai.core.ai.costs.writer import CostWriter, WorkSender, record_cost_handler
from shosai.core.ai.metrics import AiMetrics
from shosai.core.ai.port import AiProviders
from shosai.core.ai.pricing.prices import PriceBook
from shosai.core.ai.recording import CallRecorder
from shosai.core.config.loading import Settings
from shosai.core.db.transactions import HomeTransactions
from shosai.core.exchange_rates.fetch import rate_fetch_handler
from shosai.core.exchange_rates.rates import ExchangeRates
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.tasks.declaration import TaskHandler

OUTBOUND_TIMEOUT: Final = httpx.Timeout(10.0)


@dataclass(frozen=True, slots=True)
class PlatformAi:
    """The port, the rates, the settlement hook and what core's AI tasks need."""

    providers: AiProviders
    rates: ExchangeRates
    settlements: CostSettlements
    writer: CostWriter
    transactions: HomeTransactions
    outbound: httpx.AsyncClient
    cbr_url: str

    def task_handlers(self) -> list[TaskHandler[Any]]:
        """The deferred cost record and the rate fetch, registered in every role."""
        return [
            record_cost_handler(self.writer),
            rate_fetch_handler(self.transactions, self.outbound, self.cbr_url),
        ]


@dataclass(frozen=True, slots=True)
class AiDependencies:
    """What the port is built on: the homes, the task sender, the ledger, the registry."""

    transactions: HomeTransactions
    sender: WorkSender
    effects: EffectLedger
    registry: CollectorRegistry


async def open_ai(
    settings: Settings, dependencies: AiDependencies, stack: AsyncExitStack
) -> PlatformAi:
    """Build the port over the process's clients; the clients close with the stack."""
    transactions, registry = dependencies.transactions, dependencies.registry
    outbound = httpx.AsyncClient(timeout=OUTBOUND_TIMEOUT)
    stack.push_async_callback(outbound.aclose)
    openrouter = None
    key = settings.ai.openrouter_api_key
    if key is not None:
        base_url = settings.ai.openrouter_base_url
        client = (
            openrouter_client(key.get_secret_value())
            if base_url is None
            else openrouter_client(key.get_secret_value(), str(base_url))
        )
        stack.push_async_callback(client.aclose)
        openrouter = OpenRouter(client)
    metrics = AiMetrics(registry)
    rates = ExchangeRates(transactions, registry)
    settlements = CostSettlements()
    writer = CostWriter(
        transactions, dependencies.effects, settlements, dependencies.sender, metrics
    )
    providers = AiProviders(
        openrouter, PriceBook(transactions), CallRecorder(writer, rates, metrics), metrics
    )
    return PlatformAi(
        providers=providers,
        rates=rates,
        settlements=settlements,
        writer=writer,
        transactions=transactions,
        outbound=outbound,
        cbr_url=str(settings.exchange_rates.cbr_daily_url),
    )
