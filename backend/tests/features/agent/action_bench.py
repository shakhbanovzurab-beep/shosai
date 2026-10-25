"""Leo's cards over the turn bench: decisions over HTTP, execution and sweeps (agent step 9a).

A turn whose model calls the probe's write pauses with a card; the person decides through the
actions router; an approved card runs on an inline `agent` queue, unless the bench holds it to
play a worker that never came. Times are moved in the rows themselves, as the table's owner.
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
from shosai.features.agent.application.action_decisions import ActionDecisions, ActionPayload
from shosai.features.agent.application.action_execution import ActionExecution
from shosai.features.agent.application.action_sweeps import ActionSweeps
from shosai.features.agent.application.paused_runs import PausedRuns
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
    """The `agent` queue for approved actions: carried out at once, or held."""

    execution: ActionExecution | None = None
    hold: bool = False
    sent: list[ActionPayload] = field(default_factory=list)
    running: list[asyncio.Task[None]] = field(default_factory=list)

    async def send(self, task: TaskDeclaration[ActionPayload], payload: ActionPayload) -> str:
        """Run the action in the background unless held."""
        del task
        self.sent.append(payload)
        if not self.hold and self.execution is not None and payload.user_id is not None:
            run = self.execution.run(payload.home, payload.user_id, payload.action_id)
            self.running.append(asyncio.create_task(run))
        return str(uuid.uuid4())

    async def settle(self) -> None:
        """Wait for every action sent so far."""
        await asyncio.gather(*self.running)


@dataclass(frozen=True, slots=True)
class ActionBench:
    """The turn bench with decisions, execution and sweeps over the same homes and log."""

    turns: TurnBench
    http: httpx.AsyncClient
    execution: ActionExecution
    queue: InlineActions
    parts: tuple[InlineActions, PausedRuns, ActionMetrics]

    async def sweep(self) -> int:
        """The minute's sweep, as a worker runs it."""
        async with self.turns.sweeping() as transactions:
            return await ActionSweeps(transactions, self.parts).sweep(HOME)

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
    metrics = ActionMetrics(CollectorRegistry())
    paused = PausedRuns((turn_bench.homes.transactions, parts.outbox), parts.run_log)
    queue = InlineActions()
    transactions = turn_bench.homes.transactions
    execution = ActionExecution(transactions, (turn_bench.catalog, paused, metrics))
    queue.execution = execution
    decisions = ActionDecisions(transactions, (queue, paused, metrics), wait=WAIT)
    ports = PortDirectory()
    ports.install([AUTHENTICATOR.bind(BearerOfTheTest())])
    app = build_probe_app(extra=(build_actions_router(decisions, ports),)).app
    async with client_of(app) as http:
        yield ActionBench(turn_bench, http, execution, queue, (queue, paused, metrics))
        await queue.settle()
