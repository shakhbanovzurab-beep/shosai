"""The provider port over the run's slot and the scripted providers, for the AI tests."""

import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

import httpx
import sqlalchemy as sa
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.adapters.gemini_live import GeminiLive
from shosai.core.ai.adapters.mistral_ocr import MistralOcr
from shosai.core.ai.adapters.openai_realtime import OpenAiRealtime
from shosai.core.ai.adapters.openrouter import OpenRouter
from shosai.core.ai.adapters.pyannote import JobPolling, Pyannote
from shosai.core.ai.admission import Admission, AiClients
from shosai.core.ai.calls import (
    CallClass,
    CallContext,
    CallOrigin,
    ModelRef,
    ModelRoute,
    PlatformAccount,
    Provider,
)
from shosai.core.ai.costs.settlement import CostSettlements, SettledCost
from shosai.core.ai.costs.writer import CostWriter
from shosai.core.ai.metrics import AiMetrics
from shosai.core.ai.port import AiProviders
from shosai.core.ai.pricing.prices import PriceBook
from shosai.core.ai.pricing.records import ProviderPrice
from shosai.core.ai.recording import CallRecorder
from shosai.core.ai.resilience.breakers import Breakers
from shosai.core.ai.resilience.metrics import ResilienceMetrics
from shosai.core.ai.resilience.retries import RetryBudget
from shosai.core.ai.resilience.routing import Resilience, RouteRunner
from shosai.core.ai.resilience.slots import ProviderSlots
from shosai.core.ai.results import Unit
from shosai.core.ai.sessions.live import LiveSessions
from shosai.core.ai.sessions.minutes import MinuteRows
from shosai.core.ai.spend.guard import Ceilings, SpendGuard, SpendMetrics
from shosai.core.ai.spend.kill_switch import KillSwitch
from shosai.core.db.transactions import HomeTransactions
from shosai.core.exchange_rates.rates import ExchangeRates
from shosai.core.exchange_rates.records import ExchangeRate
from shosai.core.idempotency.batch import EffectBatch
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.core.tasks.payloads import TaskPayload
from tests.core.kv.outages import closed_port, redis_url
from tests.doubles.openrouter import ScriptedOpenRouter
from tests.doubles.pyannote import ScriptedPyannote

USER_ID = uuid.UUID("0190f0f0-0000-7000-8000-0000000000a1")
ORG_ID = uuid.UUID("0190f0f0-0000-7000-8000-0000000000b1")
CHAT_MODEL = ModelRef(Provider.OPENROUTER, "probe/chat")
ROUTE = ModelRoute(CHAT_MODEL)


def context(
    effect_key: str = "probe:1",
    *,
    home: Home = Home.EU,
    consent: bool = False,
    deadline: timedelta | None = None,
) -> CallContext:
    """A user's interactive call in a company."""
    return CallContext(
        effect_key=effect_key,
        feature="probe.chat",
        call_class=CallClass.STANDARD,
        origin=CallOrigin.INTERACTIVE,
        scope=TenancyScope(home, USER_ID, ORG_ID),
        cross_border_consent=consent,
        deadline=deadline,
    )


@dataclass
class RecordingSettlement:
    """A slice's settlement that records each cost it settled, in the row's transaction."""

    name: str = "probe.settlement"
    settled: list[SettledCost] = field(default_factory=list)

    async def settle(self, session: AsyncSession, cost: SettledCost) -> None:
        """Record the cost after touching the session, as a real debit would."""
        await session.execute(sa.text("SELECT 1"))
        self.settled.append(cost)


@dataclass
class RecordingSender:
    """The task sender of the deferred record: records tasks, or fails as planned."""

    failing: bool = False
    sent: list[tuple[str, TaskPayload]] = field(default_factory=list)

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Record the task, or fail like an unreachable Valkey."""
        if self.failing:
            raise TaskQueueUnavailableError(task.queue)
        self.sent.append((task.name, payload))
        return uuid.uuid4().hex


@dataclass
class ManualClock:
    """Monotonic time a test moves by hand; its sleep moves it instead of waiting."""

    now: float = 1000.0

    def __call__(self) -> float:
        """The current reading."""
        return self.now

    async def sleep(self, seconds: float) -> None:
        """Pass the time at once."""
        self.now += seconds


@dataclass
class AiBench:
    """The port and what a test inspects around it."""

    providers: AiProviders
    openrouter: ScriptedOpenRouter
    pyannote: ScriptedPyannote
    minutes: MinuteRows
    clock: ManualClock
    settlement: RecordingSettlement
    sender: RecordingSender
    writer: CostWriter
    registry: CollectorRegistry

    def sample(self, name: str, **labels: str) -> float:
        """A metric sample, 0 when never recorded."""
        return self.registry.get_sample_value(name, labels) or 0.0


@dataclass(frozen=True)
class Doubles:
    """Provider clients and Valkey for a bench; an absent provider is disabled.

    `openrouter` replaces the scripted OpenRouter's client, for a provider with other habits.
    Without `valkey` the bench meets a Valkey that refuses every connection: standard calls
    go on unguarded and breakers stay in the process, as during a Valkey outage.
    """

    openrouter: httpx.AsyncClient | None = None
    realtime: OpenAiRealtime | None = None
    gemini: GeminiLive | None = None
    mistral: httpx.AsyncClient | None = None
    valkey: Redis | None = None
    ceilings: Ceilings | None = None
    kill_switch: bool = False


NO_DOUBLES = Doubles()
# Потолки стенда настолько высоки, что не мешают тестам, которые проверяют не деньги.
OPEN_CEILINGS = Ceilings(
    global_hour=10**12, global_day=10**12,
    platform={account.value: (10**12, 10**12) for account in PlatformAccount},
)  # fmt: skip


def unreachable_valkey() -> Redis:
    """A Valkey client whose every connection is refused at once."""
    return Redis.from_url(redis_url(closed_port()).get_secret_value())


def guards(valkey: Redis, registry: CollectorRegistry) -> Resilience:
    """Breakers, slots and the retry budget over the given Valkey; small slot limits."""
    metrics = ResilienceMetrics(registry)
    limits = dict.fromkeys(Provider, 4)
    return Resilience(
        breakers=Breakers(valkey, metrics),
        slots=ProviderSlots(valkey, limits, metrics, call_wait=0.2),
        retries=RetryBudget(metrics),
        metrics=metrics,
    )


def ai_bench(
    transactions: HomeTransactions, *, enabled: bool = True, doubles: Doubles = NO_DOUBLES
) -> AiBench:
    """The port over the given homes; without a key when `enabled` is False."""
    registry = CollectorRegistry()
    metrics = AiMetrics(registry)
    settlement = RecordingSettlement()
    settlements = CostSettlements()
    settlements.install([settlement])
    sender = RecordingSender()
    effect_keys = EffectKeyMetrics(registry)
    effects = (EffectLedger(effect_keys), EffectBatch(effect_keys))
    writer = CostWriter(transactions, effects, settlements, sender, metrics)
    recorder = CallRecorder(writer, ExchangeRates(transactions, registry), metrics)
    clock = ManualClock()
    minutes = MinuteRows(recorder, clock=clock)
    scripted, diarizer = ScriptedOpenRouter(), ScriptedPyannote()
    polling = JobPolling(patience=120.0, clock=clock, sleep=clock.sleep)
    clients = AiClients(
        openrouter=OpenRouter(doubles.openrouter or scripted.client()) if enabled else None,
        pyannote=(
            Pyannote(diarizer.api_client(), diarizer.upload_client(), polling) if enabled else None
        ),
        openai_realtime=doubles.realtime,
        gemini_live=doubles.gemini,
        mistral=MistralOcr(doubles.mistral) if enabled and doubles.mistral else None,
    )
    valkey = doubles.valkey or unreachable_valkey()
    spend = SpendGuard(
        valkey, doubles.ceilings or OPEN_CEILINGS,
        KillSwitch(valkey, forced=doubles.kill_switch), SpendMetrics(registry),
    )  # fmt: skip
    writer.observe(spend.count)
    runner = RouteRunner(
        Admission(PriceBook(transactions), metrics), recorder, guards(valkey, registry), spend,
        metrics,
    )  # fmt: skip
    sessions = LiveSessions(minutes, spend, connect_timeout=5.0, renew_every=0.2)
    providers = AiProviders(clients, runner, sessions)
    return AiBench(
        providers, scripted, diarizer, minutes, clock, settlement, sender, writer, registry
    )


async def set_prices(transactions: HomeTransactions, model: ModelRef, **prices: str) -> None:
    """Prices in force for a model, by unit value: `input_token="0.000001"`."""
    rows = [
        {"id": uuid.uuid7(), "provider": model.provider.value, "model": model.model,
         "unit": Unit(unit).value, "price_usd": Decimal(price),
         "effective_from": sa.func.now() - timedelta(minutes=1), "source": "operator"}
        for unit, price in prices.items()
    ]  # fmt: skip
    async with transactions.begin(TenancyScope(Home.EU)) as session:
        await session.execute(sa.insert(ProviderPrice).values(rows))


async def set_rate(transactions: HomeTransactions, value: str) -> None:
    """A USD/RUB rate fetched now."""
    async with transactions.begin(TenancyScope(Home.EU)) as session:
        await session.execute(
            sa.insert(ExchangeRate).values(
                id=uuid.uuid7(),
                currency_pair="USD/RUB",
                rate=Decimal(value),
                source="cbr",
                fetched_at=sa.func.now(),
            )
        )
