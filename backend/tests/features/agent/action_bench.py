"""Leo's cards over the turn bench: decisions over HTTP, execution and sweeps (agent step 9a).

A turn whose model calls the probe's write pauses with a card; the person decides through the
actions router; an approved card runs on an inline `agent` queue, and so does its run's
resume for the epilogue, unless the bench holds either to play a worker that never came.
Times are moved in the rows themselves, as the table's owner.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Final

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry

from shosai.core.ports.directory import PortDirectory
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_decisions import ActionDecisions, ActionPayload
from shosai.features.agent.application.action_execution import ActionExecution
from shosai.features.agent.application.action_inbox import ActionInbox
from shosai.features.agent.application.action_sweeps import ActionSweeps
from shosai.features.agent.application.egress_calls import EgressCalls
from shosai.features.agent.application.friction_judging import FrictionJudging
from shosai.features.agent.application.paused_runs import PausedRuns
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.application.run_engine import RunEngine
from shosai.features.agent.application.run_resumption import ResumePayload
from shosai.features.agent.channels.http.actions import build_actions_router
from shosai.features.agent.infrastructure.action_metrics import ActionMetrics
from shosai.features.identity.contracts import AUTHENTICATOR
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.agent.tool_doubles import calling, saying
from tests.features.agent.turn_bench import HOME, TurnBench, stream_of
from tests.features.billing.people_bench import BearerOfTheTest, bearer
from tests.harness.connections import fetch_rows

WAIT: Final = timedelta(seconds=3)
WRITE: Final = ("tasks__create", '{"query": "Call Anna"}')


@dataclass
class InlineActions:
    """The `agent` queue for approved actions and epilogues: carried out at once, or held."""

    execution: ActionExecution | None = None
    engine: RunEngine | None = None
    hold: bool = False
    hold_resumes: bool = False
    sent: list[ActionPayload] = field(default_factory=list)
    resumes: list[ResumePayload] = field(default_factory=list)
    running: list[asyncio.Task[None]] = field(default_factory=list)

    async def send(self, task: TaskDeclaration[Any], payload: ActionPayload | ResumePayload) -> str:
        """Run the action, or the run's resume, in the background unless held."""
        if isinstance(payload, ResumePayload):
            self.resumes.append(payload)
            if not self.hold_resumes and self.engine is not None:
                self.running.append(asyncio.create_task(self.engine.resume(payload)))
            return str(uuid.uuid4())
        del task
        self.sent.append(payload)
        if not self.hold and self.execution is not None and payload.user_id is not None:
            run = self.execution.run(payload.home, payload.user_id, payload.action_id)
            self.running.append(asyncio.create_task(run))
        return str(uuid.uuid4())

    async def settle(self) -> None:
        """Wait for every action and resume sent so far, those they sent included."""
        while not all(task.done() for task in self.running):
            await asyncio.gather(*self.running)


@dataclass(frozen=True, slots=True)
class ActionBench:
    """The turn bench with decisions, execution and sweeps over the same homes and log."""

    turns: TurnBench
    http: httpx.AsyncClient
    execution: ActionExecution
    queue: InlineActions
    parts: tuple[InlineActions, PausedRuns, ActionMetrics]
    registry: CollectorRegistry
    judging: FrictionJudging

    async def sweep(self) -> int:
        """The minute's sweep, as a worker runs it."""
        async with self.turns.sweeping() as transactions:
            return await ActionSweeps(transactions, self.parts, judging=self.judging).sweep(HOME)

    async def paused_turn(self, person: uuid.UUID, text: str = "Make the task.") -> dict[str, Any]:
        """A turn whose model proposes the probe's write: its thread, run and card."""
        thread = await self.turns.thread(person)
        self.turns.model.calls.clear()
        self.turns.model.scripts = [calling(WRITE), saying("Done.")]
        events = stream_of(await self.turns.ask(person, thread, text))
        card = next(data["action"] for kind, _, data in events if kind == "action.proposed")
        return {"thread": thread, "events": events, "card": card, "run_id": events[0][2]["run_id"]}

    async def decide(
        self, person: uuid.UUID, card: dict[str, Any], verb: str, nonce: str | None = None
    ) -> httpx.Response:
        """The person's approve or reject over HTTP."""
        return await self.http.post(
            f"/v1/agent/actions/{card['id']}/{verb}",
            json={"nonce": nonce or card["nonce"]},
            headers=bearer((HOME, person)),
        )

    async def rows(self, sql: str, *params: object) -> list[dict[str, Any]]:
        """Rows as the table's owner reads them."""
        return [dict(row) for row in await fetch_rows(self.turns.connection, sql, params)]

    async def move(self, sql: str, *params: object) -> None:
        """Change rows as the table's owner: a clock moved in the data."""
        await self.turns.connection.execute(sql, params)


@pytest_asyncio.fixture
async def action_bench(turn_bench: TurnBench) -> AsyncIterator[ActionBench]:
    """Decisions over HTTP, execution and sweeps beside the turn bench."""
    parts = turn_bench.parts
    registry = CollectorRegistry()
    metrics = ActionMetrics(registry)
    queue = InlineActions(engine=turn_bench.queue.engine)
    cards = ActionCards(turn_bench.catalog, turn_bench.ports)
    paused = PausedRuns(
        (turn_bench.homes.transactions, parts.outbox), (parts.run_log, parts.frames), (queue, cards)
    )
    transactions = turn_bench.homes.transactions
    egress = EgressCalls(ResultPages(transactions, turn_bench.ports))
    execution = ActionExecution(transactions, (turn_bench.catalog, paused, metrics, egress))
    queue.execution = execution
    judging = FrictionJudging(turn_bench.ports, cards, transactions)
    decisions = ActionDecisions(transactions, (queue, paused, metrics), wait=WAIT, judging=judging)
    ports = PortDirectory()
    ports.install([AUTHENTICATOR.bind(BearerOfTheTest())])
    inbox = ActionInbox(transactions, cards)
    app = build_probe_app(extra=(build_actions_router((decisions, inbox), ports),)).app
    async with client_of(app) as http:
        yield ActionBench(
            turn_bench, http, execution, queue, (queue, paused, metrics), registry, judging
        )
        await queue.settle()
