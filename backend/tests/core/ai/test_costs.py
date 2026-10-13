"""A call writes one cost row; a replay writes none and settles nothing again (inv-9, ADR 0035)."""

from decimal import Decimal

import pytest

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, PlatformAccount
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import ChatMessage, ChatRequest, RerankRequest, Role, TextPart
from shosai.core.kernel.homes import Home
from tests.core.ai.bench import (
    CHAT_MODEL,
    ROUTE,
    USER_ID,
    ai_bench,
    context,
    set_prices,
    set_rate,
)
from tests.doubles.openrouter import chat_answer, rerank_answer, usage
from tests.harness.connections import Connection, fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

QUESTION = ChatRequest(
    messages=(ChatMessage(Role.USER, (TextPart("What changed?"),)),), max_output_tokens=200
)
CHAT_PRICES = {
    "input_token": "0.000001",
    "cached_input_token": "0.00000025",
    "output_token": "0.000004",
}


async def cost_rows(connection: Connection) -> list[dict[str, object]]:
    """Every cost row of a home."""
    rows = await fetch_rows(
        connection,
        "SELECT effect_key, payer, platform_account, user_id, kind, cost_usd, cost_source, "
        "cost_rub, exchange_rate_used, input_tokens, cached_tokens, output_tokens, units, unit "
        "FROM provider_costs ORDER BY created_at",
    )
    return [dict(row) for row in rows]


async def test_a_call_writes_one_row_and_a_replay_writes_none_and_settles_once(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await set_prices(homes.transactions, CHAT_MODEL, **CHAT_PRICES)
    await set_rate(homes.transactions, "92.5000")
    bench = ai_bench(homes.transactions)
    for _ in range(2):
        bench.openrouter.answer(
            "chat/completions", chat_answer("Two things.", usage(120, 30, cost=0.0123))
        )

    first = await bench.providers.chat(context("turn:42"), ROUTE, QUESTION)
    second = await bench.providers.chat(context("turn:42"), ROUTE, QUESTION)

    [row] = await cost_rows(run_slot.claimed.connections[Home.EU])
    assert (first.text, second.text) == ("Two things.", "Two things.")
    assert (row["effect_key"], row["payer"], row["user_id"], row["kind"]) == (
        "turn:42", "user", USER_ID, "chat",
    )  # fmt: skip
    assert (row["cost_usd"], row["cost_source"]) == (Decimal("0.0123"), "reported")
    assert (row["exchange_rate_used"], row["cost_rub"]) == (Decimal("92.5000"), Decimal("1.14"))
    assert (row["input_tokens"], row["output_tokens"]) == (120, 30)
    assert [cost.cost_usd for cost in bench.settlement.settled] == [Decimal("0.0123")]
    assert bench.sample("shosai_ai_cost_rows_recorded_total", source="reported") == 1


async def test_a_model_without_a_price_is_refused_before_it_is_called(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await set_prices(homes.transactions, CHAT_MODEL, input_token="0.000001")
    bench = ai_bench(homes.transactions)

    with pytest.raises(AiCallError) as raised:
        await bench.providers.chat(context(), ROUTE, QUESTION)

    assert raised.value.failure is AiFailure.MODEL_UNPRICED
    assert bench.openrouter.requests == []
    assert await cost_rows(run_slot.claimed.connections[Home.EU]) == []
    assert bench.sample("shosai_ai_calls_refused_total", kind="chat", code="model_unpriced") == 1


async def test_without_a_reported_cost_the_row_is_priced_from_the_units(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await set_prices(homes.transactions, CHAT_MODEL, **CHAT_PRICES, request="0.002")
    bench = ai_bench(homes.transactions)
    bench.openrouter.answer("chat/completions", chat_answer("ok", usage(1000, 100, cached=400)))
    bench.openrouter.answer(
        "rerank", rerank_answer([(1, 0.9), (0, 0.2)], search_units=3, cost=None)
    )

    await bench.providers.chat(context("chat:1"), ROUTE, QUESTION)
    ranking = await bench.providers.rerank(
        context("rerank:1"), ROUTE, RerankRequest("budget", ("a", "b"))
    )

    chat, rerank = await cost_rows(run_slot.claimed.connections[Home.EU])
    # 600 свежих × 0.000001 + 400 из кэша × 0.00000025 + 100 × 0.000004.
    assert (chat["cost_usd"], chat["cost_source"]) == (Decimal("0.0011000000"), "priced")
    assert (rerank["units"], rerank["unit"], rerank["cost_usd"]) == (
        Decimal("3.000"), "request", Decimal("0.0060000000"),
    )  # fmt: skip
    assert [document.index for document in ranking.documents] == [1, 0]
    assert chat["cost_rub"] is None
    assert bench.sample("shosai_ai_reported_cost_missing_total", kind="rerank") == 1
    assert bench.sample("shosai_ai_cost_rows_without_rate_total") == 2


async def test_a_russian_home_call_needs_the_cross_border_consent(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await set_prices(homes.transactions, CHAT_MODEL, **CHAT_PRICES)
    bench = ai_bench(homes.transactions)
    bench.openrouter.answer("chat/completions", chat_answer("ok", usage(10, 2, cost=0.001)))

    with pytest.raises(AiCallError) as raised:
        await bench.providers.chat(context(home=Home.RU), ROUTE, QUESTION)
    await bench.providers.chat(context(home=Home.RU, consent=True), ROUTE, QUESTION)

    assert raised.value.failure is AiFailure.CONSENT_REQUIRED
    assert len(bench.openrouter.requests) == 1
    assert len(await cost_rows(run_slot.claimed.connections[Home.RU])) == 1
    assert await cost_rows(run_slot.claimed.connections[Home.EU]) == []


async def test_a_platform_call_is_charged_to_its_account_in_the_eu_home(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await set_prices(homes.transactions, CHAT_MODEL, **CHAT_PRICES)
    bench = ai_bench(homes.transactions)
    bench.openrouter.answer("chat/completions", chat_answer("ok", usage(10, 2, cost=0.001)))
    demo = CallContext(
        effect_key="demo:visitor-1:1", feature="site.demo", call_class=CallClass.STANDARD,
        origin=CallOrigin.INTERACTIVE, platform_account=PlatformAccount.LANDING_DEMO,
    )  # fmt: skip

    await bench.providers.chat(demo, ROUTE, QUESTION)

    [row] = await cost_rows(run_slot.claimed.connections[Home.EU])
    assert (row["payer"], row["platform_account"], row["user_id"]) == (
        "platform", "landing_demo", None,
    )  # fmt: skip


async def test_a_disabled_provider_refuses_every_call(homes: DatabaseAccess) -> None:
    bench = ai_bench(homes.transactions, enabled=False)

    with pytest.raises(AiCallError) as raised:
        await bench.providers.chat(context(), ROUTE, QUESTION)

    assert raised.value.failure is AiFailure.MODEL_UNAVAILABLE
