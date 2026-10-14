"""The guards on their own: the retry budget, breakers and provider slots across processes."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import ConnectionPool, Redis

from shosai.core.ai.calls import CallClass, ModelRef, Provider
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.resilience.breakers import (
    FAILURES_TO_OPEN,
    Breakers,
    Gate,
    LocalBreaker,
    model_part,
)
from shosai.core.ai.resilience.metrics import ResilienceMetrics
from shosai.core.ai.resilience.retries import RetryBudget
from shosai.core.ai.resilience.slots import ProviderSlots
from shosai.core.kv.keys import build_key
from tests.core.ai.bench import unreachable_valkey
from tests.core.kv.outages import LateAnswerValkey

MODEL = ModelRef(Provider.OPENROUTER, "probe/chat:free")


class Clock:
    """Time a test moves by hand."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        """The current reading."""
        return self.now


def other_process(valkey: Redis) -> Redis:
    """A second client of the same Valkey database, as another process of the plane has.

    The client owns its pool, so closing it closes its connections.
    """
    pool = ConnectionPool(**valkey.connection_pool.connection_kwargs)
    return Redis.from_pool(pool)


def test_retries_stay_within_a_fifth_of_the_calls_plus_three() -> None:
    clock = Clock()
    budget = RetryBudget(ResilienceMetrics(CollectorRegistry()), clock=clock)

    quiet = [budget.spend(Provider.OPENROUTER) for _ in range(4)]
    for _ in range(10):
        budget._note(budget._calls, Provider.OPENROUTER)
    busy = [budget.spend(Provider.OPENROUTER) for _ in range(3)]
    clock.now += 11
    later = budget.spend(Provider.OPENROUTER)

    assert quiet == [True, True, True, False]
    # Десять вызовов дают ещё два повтора: 3 + 20% от 10 = 5 за окно.
    assert busy == [True, True, False]
    assert later is True


async def test_a_retryable_failure_is_sent_once_more_and_a_final_one_is_not() -> None:
    budget = RetryBudget(ResilienceMetrics(CollectorRegistry()))
    sent: list[str] = []

    async def flaky() -> str:
        sent.append("call")
        if len(sent) == 1:
            raise AiCallError(AiFailure.PROVIDER_ERROR, retryable=True)
        return "answer"

    async def refused() -> str:
        sent.append("refused")
        raise AiCallError(AiFailure.CONTENT_REFUSED)

    answer = await budget.attempt(Provider.OPENROUTER, flaky)
    with pytest.raises(AiCallError):
        await budget.attempt(Provider.OPENROUTER, refused)

    assert (answer, sent) == ("answer", ["call", "call", "refused"])


def test_a_local_breaker_opens_on_five_failures_and_lets_one_probe_through() -> None:
    breaker = LocalBreaker()

    opened = [breaker.failed(float(moment)) for moment in range(FAILURES_TO_OPEN)]
    during = breaker.allow(10.0)
    after = [breaker.allow(30.0), breaker.allow(30.5)]
    reopened = breaker.failed(31.0)

    assert opened == [False, False, False, False, True]
    assert during is Gate.OPEN
    assert after == [Gate.PROBE, Gate.OPEN]
    assert (reopened, breaker.allow(40.0)) == (True, Gate.OPEN)


def test_failures_spread_beyond_the_window_do_not_open_a_breaker() -> None:
    breaker = LocalBreaker()

    opened = [breaker.failed(moment * 10.0) for moment in range(FAILURES_TO_OPEN * 2)]

    assert not any(opened)
    assert breaker.allow(200.0) is Gate.CLOSED


async def test_a_breaker_opened_by_one_process_stops_the_others(valkey: Redis) -> None:
    first = Breakers(valkey, ResilienceMetrics(CollectorRegistry()))
    second_client = other_process(valkey)
    second = Breakers(second_client, ResilienceMetrics(CollectorRegistry()))
    try:
        before = await second.allow(MODEL)
        for _ in range(FAILURES_TO_OPEN):
            await first.failed(MODEL)
        after = await second.allow(MODEL)
        other_model = await second.allow(ModelRef(Provider.OPENROUTER, "probe/other"))
    finally:
        await second_client.aclose()

    assert (before, after, other_model) == (Gate.CLOSED, Gate.OPEN, Gate.CLOSED)


async def test_a_probe_s_answer_closes_the_breaker_for_every_process(valkey: Redis) -> None:
    breakers = Breakers(valkey, ResilienceMetrics(CollectorRegistry()))
    state = build_key("ai", "breaker", "openrouter", model_part(MODEL))
    # Срок открытия уже прошёл: выключатель пропускает одну пробу.
    await valkey.hset(state, "open_until", 1)

    gates = [await breakers.allow(MODEL), await breakers.allow(MODEL)]
    await breakers.succeeded(MODEL, gates[0])

    assert gates == [Gate.PROBE, Gate.OPEN]
    assert await breakers.allow(MODEL) is Gate.CLOSED


@asynccontextmanager
async def held(slots: ProviderSlots, count: int, call_class: CallClass) -> AsyncIterator[None]:
    """`count` slots of OpenRouter held for the block."""
    async with AsyncExitStack() as stack:
        for _ in range(count):
            await stack.enter_async_context(
                slots.held(Provider.OPENROUTER, call_class, session=True)
            )
        yield


async def test_the_semaphore_holds_its_limit_across_two_processes(valkey: Redis) -> None:
    limits = dict.fromkeys(Provider, 2)
    first = ProviderSlots(valkey, limits, ResilienceMetrics(CollectorRegistry()), call_wait=0.2)
    second_client = other_process(valkey)
    second = ProviderSlots(
        second_client, limits, ResilienceMetrics(CollectorRegistry()), call_wait=0.2
    )
    try:
        async with held(first, 2, CallClass.STANDARD):
            with pytest.raises(AiCallError) as session:
                async with second.held(Provider.OPENROUTER, CallClass.STANDARD, session=True):
                    pytest.fail("сверх предела")
            with pytest.raises(AiCallError) as call:
                async with second.held(Provider.OPENROUTER, CallClass.ESSENTIAL, session=False):
                    pytest.fail("сверх предела")
            async with second.held(Provider.PYANNOTE, CallClass.STANDARD, session=True):
                other_provider = True
        async with second.held(Provider.OPENROUTER, CallClass.STANDARD, session=True):
            freed = True
    finally:
        await second_client.aclose()

    assert (session.value.failure, call.value.failure) == (
        AiFailure.RETRY_LATER, AiFailure.RATE_LIMITED,
    )  # fmt: skip
    assert other_provider
    assert freed


async def test_a_call_waits_for_a_slot_freed_meanwhile(valkey: Redis) -> None:
    slots = ProviderSlots(
        valkey, dict.fromkeys(Provider, 1), ResilienceMetrics(CollectorRegistry()), call_wait=1.0
    )
    freed = asyncio.Event()

    async def hold_briefly() -> None:
        async with slots.held(Provider.OPENROUTER, CallClass.STANDARD, session=True):
            freed.set()
            await asyncio.sleep(0.2)

    holder = asyncio.create_task(hold_briefly())
    await freed.wait()
    async with slots.held(Provider.OPENROUTER, CallClass.STANDARD, session=False):
        taken = True
    await holder

    assert taken


async def test_a_slot_of_a_dead_process_is_taken_back(valkey: Redis) -> None:
    slots = ProviderSlots(
        valkey, dict.fromkeys(Provider, 1), ResilienceMetrics(CollectorRegistry()), call_wait=0.1
    )
    # Слот процесса, умершего три минуты назад: пульса нет дольше 120 с.
    await valkey.zadd(build_key("ai", "slots", "openrouter"), {"dead": 1})

    async with slots.held(Provider.OPENROUTER, CallClass.STANDARD, session=True):
        taken = True

    assert taken
    assert await valkey.zscore(build_key("ai", "slots", "openrouter"), "dead") is None


@pytest.mark.parametrize(
    ("call_class", "decision"),
    [
        (CallClass.ESSENTIAL, "unguarded"),
        (CallClass.STANDARD, "unguarded"),
        (CallClass.EXPENSIVE, "refused"),
    ],
)
async def test_without_valkey_only_expensive_calls_are_refused(
    call_class: CallClass, decision: str
) -> None:
    client = unreachable_valkey()
    registry = CollectorRegistry()
    slots = ProviderSlots(client, dict.fromkeys(Provider, 1), ResilienceMetrics(registry))
    went: AiFailure | None = None
    try:
        async with slots.held(Provider.OPENROUTER, call_class, session=False):
            went = None
    except AiCallError as refused:
        went = refused.failure
    finally:
        await client.aclose()

    assert went is (None if decision == "unguarded" else AiFailure.EXPENSIVE_PAUSED)
    assert (
        registry.get_sample_value(
            "shosai_ai_provider_slots_total", {"provider": "openrouter", "decision": decision}
        )
        == 1
    )


async def test_a_slot_taken_after_the_deadline_is_given_back(valkey: Redis) -> None:
    late = LateAnswerValkey(connection_pool=valkey.connection_pool)
    slots = ProviderSlots(late, dict.fromkeys(Provider, 1), ResilienceMetrics(CollectorRegistry()))

    async with slots.held(Provider.OPENROUTER, CallClass.STANDARD, session=False):
        taken = await valkey.zcard(build_key("ai", "slots", Provider.OPENROUTER.value))

    # Иначе слот без вызова 120 с отнимал бы у провайдера единственное место.
    assert taken == 0
