"""Calls along their routes through the port: fallback, breakers, the first-byte rule."""

import json
from decimal import Decimal

import httpx
import pytest
from redis.asyncio import Redis

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRef, ModelRoute, Provider
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import (
    ChatMessage,
    ChatRequest,
    Role,
    TextPart,
)
from shosai.core.ai.resilience.breakers import FAILURES_TO_OPEN
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from tests.core.ai.bench import ORG_ID, USER_ID, AiBench, Doubles, ai_bench, context, set_prices
from tests.core.ai.test_decisions import SOON, TICKET, delivered, recorded
from tests.doubles.openrouter import chat_answer, stream_answer, usage
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

PRIMARY = ModelRef(Provider.OPENROUTER, "probe/primary")
FALLBACK = ModelRef(Provider.OPENROUTER, "probe/fallback")
ROUTE = ModelRoute(PRIMARY, (FALLBACK,))
QUESTION = ChatRequest(messages=(ChatMessage(Role.USER, (TextPart("Hi?"),)),), max_output_tokens=20)
BUSY = httpx.Response(502, json={"error": {"message": "Bad gateway"}})
BROKEN = httpx.Response(500, json={"error": {"message": "Internal error"}})


async def routed(homes: DatabaseAccess, valkey: Redis) -> AiBench:
    """A bench over the slot's Valkey with both models of the route priced."""
    for model in (PRIMARY, FALLBACK):
        await set_prices(homes.transactions, model, input_token="0.000001", output_token="0.000002")
    return ai_bench(homes.transactions, doubles=Doubles(valkey=valkey))


def models_asked(bench: AiBench) -> list[str]:
    """The models the scripted OpenRouter was asked, in order."""
    return [str(body["model"]) for body in bench.openrouter.bodies("chat/completions")]


async def rows(run_slot: RunSlot) -> list[dict[str, object]]:
    """Cost rows of the EU home."""
    found = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT effect_key, model, kind, outcome FROM provider_costs ORDER BY created_at",
    )
    return [dict(row) for row in found]


async def test_a_failing_model_hands_the_call_to_the_next_one(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    bench = await routed(homes, valkey)
    for answer in (BUSY, BUSY, chat_answer("Hello.", usage(10, 2, cost=0.0001))):
        bench.openrouter.answer("chat/completions", answer)

    result = await bench.providers.chat(context("turn:1"), ROUTE, QUESTION)

    assert result.text == "Hello."
    assert models_asked(bench) == ["probe/primary", "probe/primary", "probe/fallback"]
    assert [(row["model"], row["outcome"]) for row in await rows(run_slot)] == [
        ("probe/fallback", "ok"),
    ]  # fmt: skip
    assert bench.sample("shosai_ai_fallbacks_total", provider="openrouter", kind="chat") == 1


async def test_a_refusal_of_the_input_is_not_handed_on(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await routed(homes, valkey)
    bench.openrouter.answer(
        "chat/completions",
        httpx.Response(403, json={"error": {"message": "Input was flagged by moderation"}}),
    )

    with pytest.raises(AiCallError) as refused:
        await bench.providers.chat(context(), ROUTE, QUESTION)

    assert refused.value.failure is AiFailure.CONTENT_REFUSED
    assert models_asked(bench) == ["probe/primary"]


async def test_an_open_breaker_skips_its_model_until_it_recovers(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await routed(homes, valkey)
    for _ in range(FAILURES_TO_OPEN):
        bench.openrouter.answer("chat/completions", BROKEN)
        bench.openrouter.answer("chat/completions", chat_answer("Fine.", usage(1, 1, cost=0.0)))
    bench.openrouter.answer("chat/completions", chat_answer("Fine.", usage(1, 1, cost=0.0)))

    for turn in range(FAILURES_TO_OPEN + 1):
        await bench.providers.chat(context(f"turn:{turn}"), ROUTE, QUESTION)

    asked = models_asked(bench)
    assert asked[: FAILURES_TO_OPEN * 2] == ["probe/primary", "probe/fallback"] * FAILURES_TO_OPEN
    # Пятый сбой открыл выключатель: шестой вызов идёт сразу к запасной модели.
    assert asked[FAILURES_TO_OPEN * 2 :] == ["probe/fallback"]
    assert bench.sample(
        "shosai_ai_breaker_transitions_total",
        provider="openrouter", model="probe/primary", state="opened",
    ) == 1  # fmt: skip


async def test_an_exhausted_route_reports_its_last_failure(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await routed(homes, valkey)
    bench.openrouter.answer("chat/completions", BROKEN)
    bench.openrouter.answer(
        "chat/completions", httpx.Response(404, json={"error": {"message": "No endpoints found"}})
    )

    with pytest.raises(AiCallError) as exhausted:
        await bench.providers.chat(context(), ROUTE, QUESTION)

    assert exhausted.value.failure is AiFailure.MODEL_UNAVAILABLE
    assert models_asked(bench) == ["probe/primary", "probe/fallback"]


async def test_a_stream_moves_on_only_before_its_first_piece(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    bench = await routed(homes, valkey)
    unavailable = httpx.Response(503, json={"error": {"message": "Overloaded"}})
    for answer in (unavailable, unavailable, stream_answer(["Hel", "lo."], usage(5, 2, cost=0.0))):
        bench.openrouter.answer("chat/completions", answer)

    pieces = [d.text async for d in bench.providers.stream_chat(context("s:1"), ROUTE, QUESTION)]

    assert "".join(pieces) == "Hello."
    assert models_asked(bench) == ["probe/primary", "probe/primary", "probe/fallback"]
    assert [row["model"] for row in await rows(run_slot)] == ["probe/fallback"]


async def test_a_stream_broken_after_its_first_piece_ends_without_moving_on(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    bench = await routed(homes, valkey)
    first = {"choices": [{"delta": {"content": "Hel"}, "finish_reason": None}]}
    broken = {"error": {"message": "upstream reset"}}
    body = f"data: {json.dumps(first)}\n\ndata: {json.dumps(broken)}\n\n".encode()
    bench.openrouter.answer("chat/completions", httpx.Response(200, content=body))

    stream = bench.providers.stream_chat(context(), ROUTE, QUESTION)

    received = [(await anext(stream)).text]
    with pytest.raises(AiCallError) as broke:
        await anext(stream)

    assert received == ["Hel"]
    assert broke.value.failure is AiFailure.PROVIDER_ERROR
    assert models_asked(bench) == ["probe/primary"]
    assert bench.sample("shosai_ai_calls_without_cost_row_total") == 1


async def test_a_paid_failure_is_recorded_apart_and_the_next_model_answers(
    homes: DatabaseAccess, run_slot: RunSlot, valkey: Redis
) -> None:
    first, second = (
        ModelRef(Provider.OPENROUTER, "typesafe/jev-1.13"),
        ModelRef(Provider.OPENROUTER, "typesafe/jev-1.12"),
    )
    for model in (first, second):
        await set_prices(homes.transactions, model, input_token="0.000000042", output_token="0")
    bench = ai_bench(homes.transactions, doubles=Doubles(valkey=valkey))
    broken = recorded()
    broken["answers"]["team"]["choice"] = "legal"
    for answer in (broken, recorded()):
        bench.openrouter.answer("alpha/decisions", httpx.Response(200, json=answer))

    decision = await bench.providers.decide(
        context("ticket:3:decide", deadline=SOON), ModelRoute(first, (second,)), TICKET
    )
    await delivered(bench)

    assert decision.model == second
    assert [(row["effect_key"], row["model"], row["outcome"]) for row in await rows(run_slot)] == [
        ("ticket:3:decide:failed:0", "typesafe/jev-1.13", "failed"),
        ("ticket:3:decide", "typesafe/jev-1.12", "ok"),
    ]


async def test_without_valkey_an_expensive_call_is_refused_and_a_standard_one_goes(
    homes: DatabaseAccess,
) -> None:
    for model in (PRIMARY, FALLBACK):
        await set_prices(homes.transactions, model, input_token="0.000001", output_token="0.000002")
    bench = ai_bench(homes.transactions)
    bench.openrouter.answer("chat/completions", chat_answer("Fine.", usage(1, 1, cost=0.0)))
    expensive = CallContext(
        effect_key="premium:1", feature="probe.chat", call_class=CallClass.EXPENSIVE,
        origin=CallOrigin.INTERACTIVE, scope=TenancyScope(Home.EU, USER_ID, ORG_ID),
    )  # fmt: skip

    standard = await bench.providers.chat(context(), ModelRoute(PRIMARY), QUESTION)
    with pytest.raises(AiCallError) as refused:
        await bench.providers.chat(expensive, ModelRoute(PRIMARY), QUESTION)

    assert standard.text == "Fine."
    assert refused.value.failure is AiFailure.EXPENSIVE_PAUSED
    assert models_asked(bench) == ["probe/primary"]
    assert bench.sample("shosai_ai_calls_without_cost_row_total") == Decimal(0)
