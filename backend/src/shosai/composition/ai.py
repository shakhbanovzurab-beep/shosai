"""The AI provider port and the exchange rates of a process, built once and closed at stop.

A provider's client exists only with its key: without it the provider is disabled, its
calls are refused (`model_unavailable`) and the start says so in the log; the gate requires
the keys outside development. A separate HTTP client serves core's own outbound calls, such
as the Central Bank's rates. The minute rows of live sessions are flushed while the process
runs and once more at stop, before the databases close.
"""

from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Final

import httpx
import structlog
from prometheus_client import CollectorRegistry
from pydantic import HttpUrl, SecretStr

from shosai.core.ai.adapters.gemini_live import GEMINI_API, GeminiLive, gemini_client
from shosai.core.ai.adapters.openai_realtime import OPENAI_REALTIME, OpenAiRealtime
from shosai.core.ai.adapters.openrouter import OPENROUTER_API, OpenRouter, openrouter_client
from shosai.core.ai.adapters.pyannote import (
    PYANNOTE_API,
    JobPolling,
    Pyannote,
    pyannote_client,
    upload_client,
)
from shosai.core.ai.costs.settlement import CostSettlements
from shosai.core.ai.costs.writer import CostWriter, WorkSender, record_cost_handler
from shosai.core.ai.metrics import AiMetrics
from shosai.core.ai.port import AiClients, AiProviders
from shosai.core.ai.pricing.prices import PriceBook
from shosai.core.ai.recording import CallRecorder
from shosai.core.ai.sessions.live import LiveSessions
from shosai.core.ai.sessions.minutes import MinuteRows
from shosai.core.config.loading import Settings
from shosai.core.config.sections import AiSettings
from shosai.core.db.transactions import HomeTransactions
from shosai.core.exchange_rates.fetch import rate_fetch_handler
from shosai.core.exchange_rates.rates import ExchangeRates
from shosai.core.idempotency.batch import EffectBatch
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.tasks.declaration import TaskHandler

OUTBOUND_TIMEOUT: Final = httpx.Timeout(10.0)
log = structlog.stdlib.get_logger(__name__)


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
    batch: EffectBatch
    registry: CollectorRegistry


def provider_client(
    name: str,
    key: SecretStr | None,
    base_url: HttpUrl | None,
    build: tuple[str, Callable[[str, str], httpx.AsyncClient]],
    stack: AsyncExitStack,
) -> httpx.AsyncClient | None:
    """The client of a provider with a key, closed with the stack; None and a log line without."""
    if key is None:
        log.warning("Провайдер ИИ выключен: нет ключа", provider=name)
        return None
    default_url, factory = build
    client = factory(key.get_secret_value(), default_url if base_url is None else str(base_url))
    stack.push_async_callback(client.aclose)
    return client


def open_clients(settings: Settings, stack: AsyncExitStack) -> AiClients:
    """The provider adapters of the process."""
    ai = settings.ai
    openrouter = provider_client(
        "openrouter",
        ai.openrouter_api_key,
        ai.openrouter_base_url,
        (OPENROUTER_API, openrouter_client),
        stack,
    )
    pyannote = provider_client(
        "pyannote",
        ai.pyannote_api_key,
        ai.pyannote_base_url,
        (PYANNOTE_API, pyannote_client),
        stack,
    )
    diarizer = None
    if pyannote is not None:
        uploads = upload_client()
        stack.push_async_callback(uploads.aclose)
        diarizer = Pyannote(pyannote, uploads, JobPolling())
    return AiClients(
        openrouter=OpenRouter(openrouter) if openrouter is not None else None,
        pyannote=diarizer,
        openai_realtime=realtime_client(ai),
        gemini_live=gemini_live(ai, stack),
    )


def realtime_client(ai: AiSettings) -> OpenAiRealtime | None:
    """OpenAI Realtime with its key; a socket per session, nothing to close at stop."""
    if ai.openai_api_key is None:
        log.warning("Провайдер ИИ выключен: нет ключа", provider="openai")
        return None
    url = OPENAI_REALTIME if ai.openai_realtime_url is None else str(ai.openai_realtime_url)
    return OpenAiRealtime(ai.openai_api_key.get_secret_value(), url)


def gemini_live(ai: AiSettings, stack: AsyncExitStack) -> GeminiLive | None:
    """Gemini Live with its key; its client closes with the stack."""
    if ai.google_live_api_key is None:
        log.warning("Провайдер ИИ выключен: нет ключа", provider="google")
        return None
    base_url = GEMINI_API if ai.google_live_base_url is None else str(ai.google_live_base_url)
    client = gemini_client(ai.google_live_api_key.get_secret_value(), base_url)
    stack.callback(client.close)
    stack.push_async_callback(client.aio.aclose)
    return GeminiLive(client)


async def open_ai(
    settings: Settings, dependencies: AiDependencies, stack: AsyncExitStack
) -> PlatformAi:
    """Build the port over the process's clients; the clients close with the stack."""
    transactions, registry = dependencies.transactions, dependencies.registry
    outbound = httpx.AsyncClient(timeout=OUTBOUND_TIMEOUT)
    stack.push_async_callback(outbound.aclose)
    clients = open_clients(settings, stack)
    metrics = AiMetrics(registry)
    rates = ExchangeRates(transactions, registry)
    settlements = CostSettlements()
    writer = CostWriter(
        transactions,
        (dependencies.effects, dependencies.batch),
        settlements,
        dependencies.sender,
        metrics,
    )
    recorder = CallRecorder(writer, rates, metrics)
    minutes = MinuteRows(recorder)
    await stack.enter_async_context(minutes.running())
    providers = AiProviders(
        clients, PriceBook(transactions), recorder, LiveSessions(minutes), metrics
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
