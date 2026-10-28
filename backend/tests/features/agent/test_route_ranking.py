"""A turn's toolsets ranked by a bound router beside the rule (decisions step 6; DL-D3).

This module's archive (≈ 3 200 tokens) fits the room only before the others: in the fixed
order the rule only names it, so the router is asked, and ranked first it is offered. Since
meetings' toolset (meetings A13) the real catalog outgrows the room, so every turn asks it (DL-D3).
"""

import asyncio
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Final

import pytest
from pydantic import JsonValue, create_model

from shosai.composition.features import FEATURES
from shosai.core.agent_tools.bindings import AgentTool, ReadTool
from shosai.core.agent_tools.spec import ToolEffect
from shosai.core.kernel.homes import Home
from shosai.features.agent.application.route_ranking import ONE_MS, ROUTE_WAIT
from shosai.features.agent.application.tool_registry import OFFERED_EFFECTS, wire_name
from shosai.features.agent.contracts import RouteRequest, TurnRouter
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.domain.digests import compact
from shosai.features.agent.domain.operator import offered_to
from shosai.features.agent.domain.routing import RouteFacts, ToolsetFacts, candidates, route
from tests.features.agent.tool_doubles import (
    WIDE_FIELDS,
    Gates,
    ProbeTools,
    Strict,
    calling,
    read,
    saying,
)
from tests.features.agent.turn_bench import HOME, TurnBench, stream_of
from tests.harness.connections import fetch_rows

ARCHIVE = "archive__search"
TTFT = "SELECT ttft_ms FROM agent_runs WHERE id = %s"
# 28 полей: ≈ 3 200 токенов — после остальных наборов не помещается, первым помещается.
MEDIUM: Final = create_model(
    "MediumArchiveQuery", __base__=Strict, **dict(list(WIDE_FIELDS.items())[:28])
)
MEDIUM_ARCHIVE: Final = read("archive.search", Gates(input=MEDIUM, step_detail=None))


@dataclass
class MediumArchive(ProbeTools):
    """The probe's tools with an archive that fits only when it comes first."""

    def bound(self) -> tuple[AgentTool, ...]:
        """The probe's tools, the archive's schema narrowed."""
        return tuple(
            ReadTool(MEDIUM_ARCHIVE, self.archive) if tool.spec.name == "archive.search" else tool
            for tool in super().bound()
        )


@dataclass
class RecordingRouter:
    """Answers every turn the same way, after a delay; keeps what it was asked and told."""

    answer: tuple[str, ...] | None = ("archive",)
    delay: float = 0.0
    asked: list[RouteRequest] = field(default_factory=list)
    ends: list[tuple[Home, uuid.UUID, frozenset[str]]] = field(default_factory=list)

    async def route(self, request: RouteRequest) -> tuple[str, ...] | None:
        """The answer set for the test."""
        self.asked.append(request)
        await asyncio.sleep(self.delay)
        return self.answer

    def ended(self, home: Home, run_id: uuid.UUID, called: frozenset[str]) -> None:
        """Keep what the run called."""
        self.ends.append((home, run_id, called))


@pytest.fixture
def probe_tools() -> ProbeTools:
    """The probe's tools with the medium archive."""
    return MediumArchive()


@pytest.fixture
def router() -> RecordingRouter:
    """The router bound for this module's turns."""
    return RecordingRouter()


@pytest.fixture
def turn_routers(router: RecordingRouter) -> tuple[TurnRouter, ...]:
    """The recording router beside the rule."""
    return (router,)


def offered(turn_bench: TurnBench, call: int) -> set[str]:
    """The wire names a model call was offered."""
    return {tool.name for tool in turn_bench.model.calls[call].tools}


async def test_a_ranked_toolset_fills_the_room_and_hears_what_the_run_called(
    turn_bench: TurnBench, router: RecordingRouter
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [calling((ARCHIVE, "{}")), saying("Found.")]

    events = stream_of(await turn_bench.ask(person, thread, "Search the archive for the budget."))
    run_id = uuid.UUID(events[0][2]["run_id"])

    assert ARCHIVE in offered(turn_bench, 0)
    assert "core__load_toolset" in offered(turn_bench, 0)
    [request] = router.asked
    assert "archive" in [name for name, _ in request.candidates]
    assert dict(request.candidates)["archive"].startswith("archive.search: ")
    assert (request.question, request.previous, request.turn) == (
        "Search the archive for the budget.", "", 0,
    )  # fmt: skip
    assert (request.run_id, request.language, request.scope.user_id) == (run_id, "en", person)
    assert router.ends == [(HOME, run_id, frozenset({"archive"}))]


async def test_a_routed_toolset_stays_for_the_thread_s_next_turns(
    turn_bench: TurnBench, router: RecordingRouter
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [saying("Fine.")]
    await turn_bench.ask(person, thread, "What is in the archive?")
    router.answer = None
    turn_bench.model.calls.clear()
    turn_bench.model.scripts = [saying("Still fine.")]

    await turn_bench.ask(person, thread, "And now?")

    assert ARCHIVE in offered(turn_bench, 0)
    assert router.asked[1].previous == "Fine."
    assert router.asked[1].turn == 1


async def test_a_slow_router_is_not_waited_for_beyond_the_turn_s_wait(
    turn_bench: TurnBench, router: RecordingRouter
) -> None:
    router.delay = 3.0
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [saying("Without it.")]

    started = time.monotonic()
    events = stream_of(await turn_bench.ask(person, thread, "Search the archive."))
    waited = time.monotonic() - started
    run = await fetch_rows(turn_bench.connection, TTFT, (uuid.UUID(events[0][2]["run_id"]),))

    assert waited < ROUTE_WAIT.total_seconds() + 1.5
    # Первое слово ждёт роутер не дольше ROUTE_WAIT, а не его три секунды.
    assert ROUTE_WAIT // ONE_MS <= run[0]["ttft_ms"] < ROUTE_WAIT // ONE_MS + 1_000
    assert ARCHIVE not in offered(turn_bench, 0)
    assert len(router.ends) == 1


def test_today_s_catalog_outgrows_the_room_so_the_router_ranks_what_is_left() -> None:
    specs = [spec for feature in FEATURES for spec in feature.agent_tools]
    sizes: Counter[str] = Counter()
    reads: Counter[str] = Counter()
    for spec in specs:
        # Ход человека: наборы оператора платформы (`platform`, `images`) ему не предлагаются.
        if spec.effect in OFFERED_EFFECTS and offered_to(spec.toolset, spec.name, operator=False):
            schema: dict[str, JsonValue] = {
                "name": wire_name(spec.name), "description": spec.description,
                "parameters": spec.input_schema(),
            }  # fmt: skip
            tokens = estimate_tokens(compact(schema))
            sizes[spec.toolset] += tokens
            reads[spec.toolset] += 0 if spec.effect is ToolEffect.WRITE else tokens
    facts = RouteFacts(tuple(ToolsetFacts(n, sizes[n], read_tokens=reads[n]) for n in sizes))

    chosen = route(facts)
    left = set(candidates(facts)) - set(chosen.selected) - set(chosen.reading)
    ranked = route(facts, tuple(sorted(left)))

    assert left
    assert left <= set(ranked.selected) | set(ranked.reading)


def test_ranked_toolsets_fill_the_room_first_and_the_route_keeps_the_fixed_order() -> None:
    toolsets = (
        ToolsetFacts("core", 500),
        ToolsetFacts("notes", 2_200, read_tokens=1_000),
        ToolsetFacts("tasks", 2_900, read_tokens=1_000),
        ToolsetFacts("files", 1_000, read_tokens=400),
        ToolsetFacts("account", 450),
    )
    facts = RouteFacts(toolsets, cap=2_000)

    plain, ranked = route(facts), route(facts, ranked=("account", "tasks"))

    assert (plain.selected, plain.reading) == (("core",), ("notes", "files"))
    assert (ranked.selected, ranked.reading) == (("core", "account"), ("tasks",))
    assert candidates(facts) == ("notes", "tasks", "files", "account")
