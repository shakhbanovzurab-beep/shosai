"""A scenario through Leo's real turn, for a person who exists only for the run (AG-D8).

The runner admits the question as the API does and drives the run as an agent worker does —
the same starter, engine, context builder, routing, rounds, wrapper and sources — with only
the model and the world around the person swapped: the scripted double or a real model behind a
recorder, the scenario's answers behind the slices' tools. What the run streamed, what the
tools received and what the model read are gathered into `Observed`; the person's rows and
keys are then erased through the slices' erasure handlers. Runs of different people may go at
once: each person's turn is driven by its own engine.
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any
from uuid import UUID

from opentelemetry.trace import NoOpTracer
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.account_data.handlers import AccountDataHandler, AccountRef
from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.agent_tools.spec import ToolSpec
from shosai.core.ai.calls import ModelRoute
from shosai.core.db.transactions import HomeTransactions
from shosai.core.documents.extraction import DocumentReader
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_proposal import ActionProposer
from shosai.features.agent.application.eval_model import RecordingModel, tools_text
from shosai.features.agent.application.eval_observe import observed_turn
from shosai.features.agent.application.eval_stage import EvalStage, EvalTools, scenario_problems
from shosai.features.agent.application.eval_world import world_bindings
from shosai.features.agent.application.fleet_presence import present_in_fleet
from shosai.features.agent.application.model_stream import DEFAULT_PACE, Pace
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.application.run_attachments import AttachmentReader
from shosai.features.agent.application.run_context import ContextBuilder, text_of
from shosai.features.agent.application.run_engine import RunEngine
from shosai.features.agent.application.run_engine_parts import EngineParts, ModelStreams
from shosai.features.agent.application.run_registry import RunRegistry
from shosai.features.agent.application.run_sources import RunSources
from shosai.features.agent.application.run_telemetry import RunTelemetry, TurnTimes
from shosai.features.agent.application.surface_digest import Subject, SubjectKind
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.tool_offer import TurnRouting
from shosai.features.agent.application.tool_registry import ToolRegistry
from shosai.features.agent.application.tool_round import ToolParts
from shosai.features.agent.application.turn_commit import TurnParts
from shosai.features.agent.application.turn_start import Page, TurnRequest, TurnStarter
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.channels.agent_tools import core_tools
from shosai.features.agent.domain.budgets import Segment
from shosai.features.agent.domain.endings import Ending
from shosai.features.agent.domain.eval_cases import EvalScenario
from shosai.features.agent.domain.eval_checks import Observed
from shosai.features.agent.domain.threads import ThreadScope
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_metrics import RunMetrics
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.tool_metrics import ToolMetrics
from shosai.features.agent.infrastructure.turn_graph import ModelAnswer, turn_graph
from shosai.features.agent.infrastructure.turn_saver import TurnSaver
from shosai.features.identity.contracts import Principal


class EvalDataError(ValueError):
    """A scenario no longer fits the tools it names."""


@dataclass(frozen=True, slots=True)
class EvalServices:
    """What the evaluation runs on: a home, Valkey, effect keys, the outbox, the slices'
    tools, and the erasure handlers that take the made-up people away again."""

    transactions: HomeTransactions
    valkey: Redis
    effects: EffectLedger
    limiter: RateLimiter
    outbox: EventOutbox
    erasers: tuple[AccountDataHandler, ...]
    specs: tuple[ToolSpec[Any, Any], ...]
    home: Home = Home.EU
    pace: Pace = DEFAULT_PACE
    # Вызовов инструментов разом: ниже пула соединений процесса, как у воркера.
    tool_calls_at_once: int = 4


class EvalTelemetry(RunTelemetry):
    """The run's telemetry, keeping each run's context segments as the engine measured them."""

    def __init__(self) -> None:
        super().__init__(RunMetrics(CollectorRegistry()), NoOpTracer())
        self.sizes: dict[UUID, dict[Segment, int]] = {}

    def ended(
        self,
        payload: TurnPayload,
        result: tuple[Ending, ModelAnswer | None],
        times: TurnTimes,
        now: datetime,
    ) -> None:
        """Note the segments, then record as a worker does."""
        self.sizes[payload.run_id] = dict(times.sizes)
        super().ended(payload, result, times, now)


class PersonEngines:
    """The `agent` queue of the evaluation: each person's turn runs at once on its engine."""

    def __init__(self) -> None:
        self.engines: dict[UUID, RunEngine] = {}

    async def send(self, task: TaskDeclaration[TurnPayload], payload: TurnPayload) -> str:
        """Drive the run to its end before answering."""
        del task
        engine = self.engines.get(payload.user_id) if payload.user_id is not None else None
        if engine is None:
            message = "ход оценки без движка своего человека"
            raise LookupError(message)
        await engine.run(payload)
        return str(payload.run_id)


class EvalRunner:
    """Runs scenarios through Leo's turn."""

    def __init__(self, services: EvalServices, route: ModelRoute) -> None:
        self._services = services
        self._stage = EvalStage()
        ports = PortDirectory()
        ports.install(world_bindings(self._stage))
        transactions, valkey = services.transactions, services.valkey
        pages = ResultPages(transactions, ports)
        catalog = AgentToolCatalog()
        catalog.install([*core_tools(pages), *EvalTools(self._stage).bind(services.specs)])
        self._tools = {
            tool.spec.name: tool for name in catalog.toolsets() for tool in catalog.toolset(name)
        }
        self._run_log, leases, self._fleet = RunLog(valkey), ThreadLeases(valkey), Fleet(valkey)
        frames = TurnSaver(valkey)
        self._registry = RunRegistry(leases, self._fleet)
        self._telemetry = EvalTelemetry()
        tools = ToolParts(
            pages, RunSources(transactions, ports), asyncio.Semaphore(services.tool_calls_at_once),
            ToolMetrics(CollectorRegistry()), NoOpTracer(),
            ActionProposer(transactions, ActionCards(catalog, ports)),
        )  # fmt: skip
        # Модель у каждого хода своя, за записью; остальное движку оценки общее.
        self._parts_with = partial(
            EngineParts, transactions=transactions, route=route, run_log=self._run_log,
            leases=leases, fleet=self._fleet, registry=self._registry, outbox=services.outbox,
            graph=turn_graph(frames), frames=frames, context=ContextBuilder(ports),
            routing=TurnRouting(ToolRegistry(catalog), ports), tools=tools,
            telemetry=self._telemetry, pace=services.pace,
            # В мире оценки вложений нет: хранилище пусто.
            attachments=AttachmentReader(transactions, ({}, DocumentReader(), pages)),
        )  # fmt: skip
        self._queue = PersonEngines()
        self._threads = Threads(transactions, (ports, services.effects))
        self._starter = TurnStarter(
            TurnParts(
                transactions, ports, services.effects, services.limiter, self._queue,
                self._run_log, leases, self._fleet, self._threads, frames,
            )
        )  # fmt: skip

    @asynccontextmanager
    async def serving(self) -> AsyncIterator[EvalRunner]:
        """The runner as a live agent worker of the fleet, for as long as it runs scenarios."""
        try:
            async with present_in_fleet(self._fleet):
                yield self
        finally:
            await self._registry.close()

    def problems(self, scenarios: Sequence[EvalScenario]) -> list[str]:
        """What in the scenarios no longer fits the tools."""
        return [problem for each in scenarios for problem in scenario_problems(each, self._tools)]

    async def run(
        self,
        scenario: EvalScenario,
        language: str,
        models: Callable[[], ModelStreams],
        *,
        turns: int = 1,
    ) -> tuple[Observed, ...]:
        """The scenario's question asked `turns` times in one thread, each turn as observed;
        `models` gives each turn its model."""
        problems = scenario_problems(scenario, self._tools)
        if problems:
            raise EvalDataError("; ".join(problems))
        principal = Principal(new_id(), self._services.home, token_version=0)
        self._stage.enter(principal.user_id, scenario, language)
        try:
            thread = await self._threads.create(principal, ThreadScope.personal(), new_id().hex)
            return tuple([await self._turn(principal, thread.id, models()) for _ in range(turns)])
        finally:
            self._stage.leave(principal.user_id)
            self._queue.engines.pop(principal.user_id, None)
            for eraser in self._services.erasers:
                await eraser.erase(AccountRef(principal.user_id, principal.home))

    async def _turn(self, principal: Principal, thread_id: UUID, model: ModelStreams) -> Observed:
        staged = self._stage.of(principal.user_id)
        if staged is None:
            message = "ход оценки без сценария"
            raise LookupError(message)
        recording = RecordingModel(model)
        self._queue.engines[principal.user_id] = RunEngine(self._parts_with(ai=recording))
        scenario, language = staged.scenario, staged.language
        subject = scenario.subject
        page = Page(
            scenario.page,
            Subject(SubjectKind(subject.kind), subject.id) if subject is not None else None,
        )
        request = TurnRequest(scenario.question(language), language, supersede=False, page=page)
        before, proposed = len(staged.runs), len(staged.proposed)
        run_id = await self._starter.start(principal, thread_id, request, new_id().hex)
        events = await self._run_log.after(run_id, 0)
        first = recording.requests[0] if recording.requests else None
        return observed_turn(
            events,
            recording,
            (tuple(staged.runs[before:]), tuple(staged.proposed[proposed:])),
            (
                self._telemetry.sizes.pop(run_id, {}),
                text_of(first.messages[0]) if first is not None else "",
                tools_text(first) if first is not None else "",
            ),
        )
