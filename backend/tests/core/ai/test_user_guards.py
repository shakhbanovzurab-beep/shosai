"""Per-user guards: two interactive streams at once, input caps, one spend alert a day."""

from collections.abc import Sequence
from contextlib import AsyncExitStack
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.decisions import DecisionRequest, NoulQuestion
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.events import UserSpendExceeded
from shosai.core.ai.requests import ChatMessage, ChatRequest, ImagePart, Role, TextPart
from shosai.core.ai.resilience.streams import StreamCap
from shosai.core.ai.spend.alert import SpendAlert
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kv.keys import build_key
from tests.core.ai.bench import (
    CHAT_MODEL,
    ROUTE,
    USER_ID,
    Doubles,
    ai_bench,
    context,
    set_prices,
    unreachable_valkey,
)
from tests.core.ai.test_spend_reports import OTHER_USER, row
from tests.core.kv.outages import LateAnswerValkey
from tests.doubles.openrouter import stream_answer, usage
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

QUESTION = ChatRequest(messages=(ChatMessage(Role.USER, (TextPart("Hi?"),)),), max_output_tokens=20)
PICTURE = ImagePart(b"\x89PNG probe", "image/png")


def of(call_class: CallClass, origin: CallOrigin = CallOrigin.INTERACTIVE) -> CallContext:
    """The bench user's call of the class and origin."""
    return replace(context(), call_class=call_class, origin=origin)


async def test_a_third_interactive_stream_is_refused_and_an_essential_one_counts(
    valkey: Redis,
) -> None:
    cap = StreamCap(valkey, cap=2)
    streams = build_key("ai", "streams", USER_ID.hex)

    async with AsyncExitStack() as held:
        for _ in range(2):
            await held.enter_async_context(cap.held(of(CallClass.STANDARD)))
        with pytest.raises(AiCallError) as third:
            await held.enter_async_context(cap.held(of(CallClass.EXPENSIVE)))
        await held.enter_async_context(cap.held(of(CallClass.STANDARD, CallOrigin.BACKGROUND)))
        await held.enter_async_context(cap.held(of(CallClass.ESSENTIAL)))
        in_flight = await valkey.zcard(streams)
    after = await valkey.zcard(streams)

    assert third.value.failure is AiFailure.RATE_LIMITED
    assert third.value.params["retry_after_seconds"] == 5
    # Две обычные и встреча: встреча пущена сверх предела, но учтена; фон не считается.
    assert (in_flight, after) == (3, 0)


@pytest.mark.parametrize("call_class", [CallClass.ESSENTIAL, CallClass.STANDARD])
async def test_without_valkey_the_cap_stops_no_call(call_class: CallClass) -> None:
    client = unreachable_valkey()
    cap = StreamCap(client, cap=0)
    try:
        async with cap.held(of(call_class)):
            went = True
    finally:
        await client.aclose()

    assert went


async def test_a_stream_over_the_cap_is_refused_before_the_provider_is_asked(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    await set_prices(
        homes.transactions, CHAT_MODEL, input_token="0.000001", output_token="0.000002"
    )
    bench = ai_bench(homes.transactions, doubles=Doubles(valkey=valkey))
    bench.openrouter.answer("chat/completions", stream_answer(["Hi."], usage(1, 1, cost=0.0)))
    cap = StreamCap(valkey, cap=2)

    async with cap.held(of(CallClass.STANDARD)), cap.held(of(CallClass.STANDARD)):
        with pytest.raises(AiCallError) as refused:
            await anext(bench.providers.stream_chat(context(), ROUTE, QUESTION))

    assert refused.value.failure is AiFailure.RATE_LIMITED
    assert bench.openrouter.requests == []


@pytest.mark.parametrize(
    "request_",
    [
        ChatRequest(messages=(ChatMessage(Role.USER, (PICTURE,) * 7),), max_output_tokens=20),
        ChatRequest(
            messages=(ChatMessage(Role.USER, (TextPart("x" * 130_000),)),), max_output_tokens=20
        ),
    ],
    ids=["seven images", "long context"],
)
async def test_an_input_over_a_cap_is_refused_before_any_provider_is_called(
    homes: DatabaseAccess, request_: ChatRequest
) -> None:
    bench = ai_bench(homes.transactions)

    with pytest.raises(AiCallError) as refused:
        await bench.providers.chat(context(), ROUTE, request_)

    assert refused.value.failure is AiFailure.INPUT_TOO_LARGE
    assert refused.value.model_text.startswith("The request is too large")
    assert bench.openrouter.requests == []


async def test_a_decision_state_over_the_context_cap_is_refused(homes: DatabaseAccess) -> None:
    bench = ai_bench(homes.transactions)
    huge = DecisionRequest(state="x" * 130_000, questions={"q": NoulQuestion("Is it urgent?")})

    with pytest.raises(AiCallError) as refused:
        await bench.providers.decide(
            replace(context(), deadline=timedelta(seconds=1)),
            ModelRoute(CHAT_MODEL), huge,
        )  # fmt: skip

    assert refused.value.failure is AiFailure.INPUT_TOO_LARGE


async def test_a_user_passing_the_threshold_yields_one_alert_a_day(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    writer = ai_bench(homes.transactions, doubles=Doubles(valkey=valkey)).writer
    outbox = EventOutbox(EventTypes([UserSpendExceeded]))
    writer.observe(SpendAlert(valkey, homes.transactions, outbox, threshold_micro=500_000).observe)
    now = datetime.now(UTC)

    for cost in ("0.30", "0.25", "0.40"):
        await writer.write(row(Home.EU, now, cost))
    await writer.write(row(Home.EU, now, "0.45", user_id=OTHER_USER))

    events = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT event_type, payload, user_id FROM outbox_messages ORDER BY id",
    )
    [alert] = [dict(event) for event in events if event["event_type"] == "ai.user_spend.exceeded"]
    assert alert["user_id"] == USER_ID
    assert alert["payload"] == {
        "user_id": str(USER_ID), "day": now.date().isoformat(),
        "spend_micro_usd": 550_000, "threshold_micro_usd": 500_000,
    }  # fmt: skip


async def test_an_alert_marker_set_after_the_deadline_is_taken_back(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    outbox = EventOutbox(EventTypes([UserSpendExceeded]))
    alerts = [
        SpendAlert(client, homes.transactions, outbox, threshold_micro=500_000)
        for client in (LateAnswerValkey(connection_pool=valkey.connection_pool), valkey)
    ]
    writer = ai_bench(homes.transactions, doubles=Doubles(valkey=valkey)).writer

    async def current_alert(entries: Sequence[CostEntry]) -> None:
        await alerts[0].observe(entries)

    writer.observe(current_alert)
    now = datetime.now(UTC)

    for cost in ("0.30", "0.25"):
        await writer.write(row(Home.EU, now, cost))
    # Тревога первого порога потерялась с ответом; её пометка не должна съесть сутки.
    alerts.pop(0)
    await writer.write(row(Home.EU, now, "0.40"))

    events = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT payload FROM outbox_messages WHERE event_type = 'ai.user_spend.exceeded'",
    )
    assert [event["payload"]["spend_micro_usd"] for event in events] == [950_000]


async def test_a_stream_place_taken_after_the_deadline_is_given_back(valkey: Redis) -> None:
    late = StreamCap(LateAnswerValkey(connection_pool=valkey.connection_pool), cap=1)

    async with late.held(of(CallClass.STANDARD)):
        in_flight = await valkey.zcard(build_key("ai", "streams", USER_ID.hex))

    # Иначе место без потока 120 с отказывало бы человеку в единственном разрешённом потоке.
    assert in_flight == 0
