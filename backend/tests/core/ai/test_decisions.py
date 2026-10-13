"""Jev decisions: the contract on a recorded answer, one row per decision, a deadline kept."""

import asyncio
import copy
import json
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from shosai.core.ai.adapters.openrouter_decisions import decision_of
from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.ai.decisions import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionRequest,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.kernel.homes import Home
from tests.core.ai.bench import AiBench, ai_bench, context, set_prices
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

JEV = ModelRef(Provider.OPENROUTER, "typesafe/jev-1.13")
RECORDED = Path(__file__).parent / "recorded" / "decisions_answer.json"
TICKET = DecisionRequest(
    state={"ticket": "Checkout fails with a 500 for card payments.", "customer_tier": "enterprise"},
    questions={
        "is_bug": NoulQuestion("Is this a defect in the product?"),
        "team": ChoiceQuestion(
            "Which team owns the fix?",
            {"account": "Sign-in and profiles", "frontend": "Screens and layout",
             "payments": "Checkout and billing"},
        ),
        "urgency": ScoreQuestion(
            "How urgent is it?",
            ("Can wait for the next release", "Needed this week", "Blocking revenue right now"),
        ),
    },
)  # fmt: skip
SOON = timedelta(seconds=2)


def recorded() -> dict[str, Any]:
    """The answer recorded from OpenRouter's reference, freshly loaded."""
    loaded = json.loads(RECORDED.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


async def rows(run_slot: RunSlot) -> list[dict[str, object]]:
    """Cost rows of the EU home."""
    found = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT kind, outcome, input_tokens, output_tokens, cost_usd, cost_source "
        "FROM provider_costs",
    )
    return [dict(row) for row in found]


async def deciding(homes: DatabaseAccess) -> AiBench:
    """A bench with Jev priced as OpenRouter lists it."""
    await set_prices(homes.transactions, JEV, input_token="0.000000042", output_token="0")
    return ai_bench(homes.transactions)


def test_the_recorded_answer_keeps_its_contract() -> None:
    decision = decision_of(recorded(), JEV, TICKET)

    assert decision.snapshot == "typesafe/jev-1.13-20260917"
    assert decision.decision_id == "gen-dec-1789738314-X5e5eKGQdvR9rblyX250"
    assert decision.answers["is_bug"] == NoulAnswer(0.96)
    team = decision.answers["team"]
    assert isinstance(team, ChoiceAnswer)
    assert (team.choice, team.confidence, team.probabilities["payments"]) == (
        "payments",
        0.75,
        0.85,
    )
    urgency = decision.answers["urgency"]
    assert isinstance(urgency, ScoreAnswer)
    assert (urgency.score, urgency.probabilities["2"]) == (1.99, 0.99)
    assert (decision.usage.input_tokens, decision.usage.reported_cost_usd) == (
        476, Decimal("0.000019992"),
    )  # fmt: skip


def without(path: tuple[str, ...]) -> Callable[[dict[str, Any]], None]:
    """A change that removes one field of the answer."""

    def change(answer: dict[str, Any]) -> None:
        node = answer
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return change


def setting(path: tuple[str, ...], value: object) -> Callable[[dict[str, Any]], None]:
    """A change that sets one field of the answer."""

    def change(answer: dict[str, Any]) -> None:
        node = answer
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return change


@pytest.mark.parametrize(
    "change",
    [
        without(("answers", "urgency")),
        without(("model",)),
        without(("usage",)),
        setting(("answers", "team", "choice"), "legal"),
        setting(("answers", "urgency", "score"), 3.5),
        setting(("answers", "is_bug", "type"), "choice"),
        setting(("answers", "is_bug", "noul"), "0.96"),
        setting(("answers", "team", "probabilities"), {"marketing": 1.0}),
        setting(("usage", "input_tokens"), "476"),
    ],
)
def test_an_answer_that_leaves_the_contract_is_refused(
    change: Callable[[dict[str, Any]], None],
) -> None:
    answer = copy.deepcopy(recorded())
    change(answer)

    with pytest.raises(AiCallError) as broken:
        decision_of(answer, JEV, TICKET)

    assert broken.value.failure is AiFailure.PROVIDER_ERROR


async def test_a_decision_writes_one_row_at_the_reported_cost(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await deciding(homes)
    bench.openrouter.answer("alpha/decisions", httpx.Response(200, json=recorded()))

    decision = await bench.providers.decide(
        context("turn:7:route", deadline=SOON), ModelRoute(JEV), TICKET
    )

    [body] = bench.openrouter.bodies("alpha/decisions")
    [row] = await rows(run_slot)
    assert body["model"] == "typesafe/jev-1.13"
    assert body["questions"]["is_bug"] == {
        "type": "noul", "instructions": "Is this a defect in the product?",
    }  # fmt: skip
    assert body["questions"]["urgency"]["criteria"][0] == "Can wait for the next release"
    assert body["questions"]["team"]["criteria"]["payments"] == "Checkout and billing"
    assert decision.snapshot == "typesafe/jev-1.13-20260917"
    assert (row["kind"], row["outcome"], row["input_tokens"]) == ("decide", "ok", 476)
    assert (row["cost_usd"], row["cost_source"]) == (Decimal("0.0000199920"), "reported")


async def test_without_a_reported_cost_a_decision_is_priced_by_its_input_tokens(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await deciding(homes)
    answer = recorded()
    del answer["usage"]["cost"]
    bench.openrouter.answer("alpha/decisions", httpx.Response(200, json=answer))

    await bench.providers.decide(context(deadline=SOON), ModelRoute(JEV), TICKET)

    [row] = await rows(run_slot)
    assert (row["cost_usd"], row["cost_source"]) == (Decimal("0.0000199920"), "priced")


async def test_a_paid_answer_out_of_contract_is_recorded_as_failed(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await deciding(homes)
    answer = recorded()
    answer["answers"]["team"]["choice"] = "legal"
    bench.openrouter.answer("alpha/decisions", httpx.Response(200, json=answer))

    with pytest.raises(AiCallError) as broken:
        await bench.providers.decide(context(deadline=SOON), ModelRoute(JEV), TICKET)

    [row] = await rows(run_slot)
    assert broken.value.failure is AiFailure.PROVIDER_ERROR
    assert (row["kind"], row["outcome"]) == ("decide", "failed")


async def test_a_decision_past_its_deadline_is_cut_without_a_late_row(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await deciding(homes)

    async def late(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1.0)
        return httpx.Response(200, json=recorded())

    slow = httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1/", transport=httpx.MockTransport(late)
    )
    bench = ai_bench(homes.transactions, client=slow)

    with pytest.raises(AiCallError) as cut:
        await bench.providers.decide(
            context(deadline=timedelta(milliseconds=50)), ModelRoute(JEV), TICKET
        )
    await asyncio.sleep(1.1)

    assert cut.value.failure is AiFailure.DEADLINE_EXCEEDED
    assert await rows(run_slot) == []


async def test_a_decision_without_its_own_deadline_is_a_caller_error(
    homes: DatabaseAccess,
) -> None:
    bench = await deciding(homes)

    with pytest.raises(ValueError, match="срок"):
        await bench.providers.decide(context(), ModelRoute(JEV), TICKET)


@pytest.mark.parametrize(
    "build",
    [
        lambda: ChoiceQuestion("Pick.", {"only": "One option"}),
        lambda: ScoreQuestion("Rate.", ("one level",)),
        lambda: NoulQuestion("True?", when_true="yes"),
        lambda: DecisionRequest(state="s", questions={}),
    ],
)
def test_a_malformed_question_is_refused(build: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match=r"\w"):
        build()
