"""Spend control: ceilings never stop essential calls, reservations hold, the kill switch."""

import asyncio
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.ai.calls import (
    CallClass,
    CallContext,
    CallOrigin,
    ModelRef,
    ModelRoute,
    PlatformAccount,
    Provider,
    SpendLimit,
    SpendPeriod,
)
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.recording import MeteredCall
from shosai.core.ai.requests import ChatMessage, ChatRequest, Role, TextPart
from shosai.core.ai.results import Unit, Usage
from shosai.core.ai.spend.counters import Payer, counters_of
from shosai.core.ai.spend.guard import Ceilings, SpendGuard, SpendMetrics
from shosai.core.ai.spend.kill_switch import KillSwitch
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.ai.bench import (
    OPEN_CEILINGS,
    ORG_ID,
    USER_ID,
    AiBench,
    Doubles,
    ai_bench,
    set_prices,
)
from tests.core.kv.outages import LateAnswerValkey
from tests.doubles.openrouter import chat_answer, usage
from tests.harness.database_access import DatabaseAccess

CHEAP = ModelRef(Provider.OPENROUTER, "probe/cheap")
PREMIUM = ModelRef(Provider.OPENROUTER, "probe/premium")
# 100 токенов на входе и 100 на выходе по $0.00001 — оценка $0.002, 2000 мкр$.
QUESTION = ChatRequest(
    messages=(ChatMessage(Role.USER, (TextPart("x" * 400),)),), max_output_tokens=100
)
PRICES = {Unit.INPUT: Decimal("0.00001"), Unit.OUTPUT: Decimal("0.00001")}


def call(
    call_class: CallClass,
    *,
    origin: CallOrigin = CallOrigin.INTERACTIVE,
    limits: tuple[SpendLimit, ...] = (),
    key: str = "probe:1",
) -> CallContext:
    """A user's call of the class, with the caller's limits."""
    return CallContext(
        effect_key=key, feature="probe.chat", call_class=call_class, origin=origin,
        scope=TenancyScope(Home.EU, USER_ID, ORG_ID), spend_limits=limits,
    )  # fmt: skip


def capped(hour: int = 10**12, day: int = 10**12, platform: int = 10**12) -> Ceilings:
    """Ceilings in micro-USD."""
    return Ceilings(
        global_hour=hour, global_day=day,
        platform={account.value: (platform, platform) for account in PlatformAccount},
    )  # fmt: skip


async def spending(
    homes: DatabaseAccess,
    valkey: Redis,
    ceilings: Ceilings = OPEN_CEILINGS,
    *,
    forced: bool = False,
) -> AiBench:
    """A bench over the slot's Valkey with both models priced and answers queued."""
    for model in (CHEAP, PREMIUM):
        await set_prices(homes.transactions, model, input_token="0.00001", output_token="0.00001")
    doubles = Doubles(valkey=valkey, ceilings=ceilings, kill_switch=forced)
    bench = ai_bench(homes.transactions, doubles=doubles)
    for _ in range(4):
        bench.openrouter.answer(
            "chat/completions", chat_answer("Fine.", usage(100, 10, cost=0.001))
        )
    return bench


async def test_no_ceiling_and_no_kill_switch_stops_an_essential_call(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await spending(homes, valkey, capped(hour=0, day=0), forced=True)

    answer = await bench.providers.chat(call(CallClass.ESSENTIAL), ModelRoute(CHEAP), QUESTION)
    with pytest.raises(AiCallError) as standard:
        await bench.providers.chat(call(CallClass.STANDARD), ModelRoute(CHEAP), QUESTION)

    assert answer.text == "Fine."
    assert standard.value.failure is AiFailure.SPEND_LIMIT


async def test_the_kill_switch_pauses_expensive_calls_or_sends_them_to_the_standard_model(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await spending(homes, valkey)
    switch = KillSwitch(valkey, forced=False)
    await switch.engage("operator-7", "Provider overbilling", timedelta(minutes=5))

    with pytest.raises(AiCallError) as paused:
        await bench.providers.chat(call(CallClass.EXPENSIVE), ModelRoute(PREMIUM), QUESTION)
    standard = await bench.providers.chat(
        call(CallClass.EXPENSIVE), ModelRoute(PREMIUM, standard=CHEAP), QUESTION
    )
    plain = await bench.providers.chat(call(CallClass.STANDARD), ModelRoute(CHEAP), QUESTION)
    state = await switch.state()
    await switch.release("operator-7")

    assert paused.value.failure is AiFailure.EXPENSIVE_PAUSED
    assert (standard.text, plain.text) == ("Fine.", "Fine.")
    asked = [body["model"] for body in bench.openrouter.bodies("chat/completions")]
    assert asked == ["probe/cheap", "probe/cheap"]
    assert (state.engaged, state.actor, state.reason) == (
        True,
        "operator-7",
        "Provider overbilling",
    )
    assert (await switch.state()).engaged is False


async def test_without_valkey_an_expensive_call_fails_closed(homes: DatabaseAccess) -> None:
    for model in (CHEAP, PREMIUM):
        await set_prices(homes.transactions, model, input_token="0.00001", output_token="0.00001")
    bench = ai_bench(homes.transactions)

    with pytest.raises(AiCallError) as paused:
        await bench.providers.chat(call(CallClass.EXPENSIVE), ModelRoute(PREMIUM), QUESTION)

    assert paused.value.failure is AiFailure.EXPENSIVE_PAUSED
    assert bench.openrouter.requests == []


def guard_over(valkey: Redis, ceilings: Ceilings) -> SpendGuard:
    """Spend control over the slot's Valkey."""
    registry = CollectorRegistry()
    return SpendGuard(valkey, ceilings, KillSwitch(valkey, forced=False), SpendMetrics(registry))


def metered(context: CallContext) -> MeteredCall:
    """A call of the cheap model as the route admits it."""
    return MeteredCall(context, CHEAP, "chat", PRICES)


ESTIMATE = Usage(input_tokens=100, output_tokens=100)


async def test_concurrent_reservations_never_pass_a_ceiling(valkey: Redis) -> None:
    guard = guard_over(valkey, OPEN_CEILINGS)
    # Потолок дня — 7000 мкр$, оценка вызова — 2000: проходят ровно три из десяти.
    context = call(CallClass.STANDARD, limits=(SpendLimit(SpendPeriod.DAY, 7000),))

    async def reserve() -> str:
        try:
            hold = await guard.reserve(metered(context), ESTIMATE)
        except AiCallError:
            return "refused"
        return "held" if hold is not None else "unguarded"

    outcomes = Counter(await asyncio.gather(*(reserve() for _ in range(10))))

    # Ответ, опоздавший за 50 мс, пускает standard-вызов без резерва (fail open, F6 §3.6);
    # резервов же не больше потолка никогда, а без опозданий их ровно три.
    assert outcomes["held"] <= 3
    assert outcomes["held"] == 3 or outcomes["unguarded"]
    assert outcomes.total() == 10


async def test_a_reservation_applied_after_the_deadline_is_taken_back(valkey: Redis) -> None:
    late = guard_over(LateAnswerValkey(connection_pool=valkey.connection_pool), OPEN_CEILINGS)
    guard = guard_over(valkey, OPEN_CEILINGS)
    context = call(CallClass.STANDARD, limits=(SpendLimit(SpendPeriod.DAY, 7000),))

    unguarded = await late.reserve(metered(context), ESTIMATE)
    holds = [await guard.reserve(metered(context), ESTIMATE) for _ in range(3)]

    # Иначе резерв без владельца держал бы 2000 из 7000 до конца аренды.
    assert unguarded is None
    assert all(hold is not None for hold in holds)


async def test_an_expired_reservation_frees_its_amount(valkey: Redis) -> None:
    guard = guard_over(valkey, replace(OPEN_CEILINGS, lease=timedelta(milliseconds=200)))
    context = call(CallClass.STANDARD, limits=(SpendLimit(SpendPeriod.HOUR, 2000),))

    first = await guard.reserve(metered(context), ESTIMATE)
    with pytest.raises(AiCallError) as full:
        await guard.reserve(metered(context), ESTIMATE)
    await asyncio.sleep(0.3)
    after_lease = await guard.reserve(metered(context), ESTIMATE)

    assert first is not None
    assert full.value.failure is AiFailure.SPEND_LIMIT
    assert after_lease is not None


async def test_a_recorded_call_fills_its_counters_once_and_frees_its_reservation(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await spending(homes, valkey)
    context = call(CallClass.EXPENSIVE, key="turn:9")

    for _ in range(2):
        await bench.providers.chat(context, ModelRoute(PREMIUM), QUESTION)

    payer = Payer(USER_ID, None, CallOrigin.INTERACTIVE, CallClass.EXPENSIVE, datetime.now(UTC))
    filled = {c.limit: await valkey.get(c.key) for c in counters_of(payer)}
    held = [await valkey.hlen(c.held) for c in counters_of(payer)]
    # Отчёт провайдера $0.001 — 1000 мкр$; повтор того же ключа ничего не добавил.
    assert set(filled.values()) == {b"1000"}
    assert set(filled) >= {"global_day", SpendPeriod.DAY, SpendPeriod.EXPENSIVE_MONTH}
    assert held == [0] * len(held)


async def test_only_interactive_calls_fill_the_user_s_own_ceilings(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await spending(homes, valkey)
    closed_day = (SpendLimit(SpendPeriod.DAY, 0),)
    closed_background = (SpendLimit(SpendPeriod.BACKGROUND_DAY, 0),)

    background = await bench.providers.chat(
        call(CallClass.STANDARD, origin=CallOrigin.BACKGROUND, limits=closed_day),
        ModelRoute(CHEAP), QUESTION,
    )  # fmt: skip
    with pytest.raises(AiCallError) as initiative:
        await bench.providers.chat(
            call(CallClass.STANDARD, origin=CallOrigin.BACKGROUND, limits=closed_background),
            ModelRoute(CHEAP), QUESTION,
        )  # fmt: skip
    with pytest.raises(AiCallError) as interactive:
        await bench.providers.chat(
            call(CallClass.STANDARD, limits=closed_day), ModelRoute(CHEAP), QUESTION
        )

    assert background.text == "Fine."
    assert initiative.value.failure is AiFailure.SPEND_LIMIT
    assert interactive.value.failure is AiFailure.SPEND_LIMIT


async def test_a_platform_account_has_its_own_cap(homes: DatabaseAccess, valkey: Redis) -> None:
    bench = await spending(homes, valkey, capped(platform=0))
    demo = CallContext(
        effect_key="demo:1", feature="site.demo", call_class=CallClass.STANDARD,
        origin=CallOrigin.SYSTEM, platform_account=PlatformAccount.LANDING_DEMO,
    )  # fmt: skip

    with pytest.raises(AiCallError) as capped_out:
        await bench.providers.chat(demo, ModelRoute(CHEAP), QUESTION)

    assert capped_out.value.failure is AiFailure.SPEND_LIMIT


async def test_a_turn_holds_its_estimate_and_its_calls_draw_on_it(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await spending(homes, valkey)
    limit = (SpendLimit(SpendPeriod.DAY, 6000),)
    leo = call(CallClass.STANDARD, limits=limit, key="turn:41")

    async with bench.providers.turn(leo, Decimal("0.005")) as turn:
        inside = await bench.providers.chat(
            replace(turn, effect_key="turn:41:1"), ModelRoute(CHEAP), QUESTION
        )
        with pytest.raises(AiCallError) as outside:
            await bench.providers.chat(
                replace(leo, effect_key="other:1"), ModelRoute(CHEAP), QUESTION
            )
    after = await bench.providers.chat(
        replace(leo, effect_key="other:2"), ModelRoute(CHEAP), QUESTION
    )

    assert inside.text == "Fine."
    assert outside.value.failure is AiFailure.SPEND_LIMIT
    assert after.text == "Fine."
