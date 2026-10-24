"""An agent worker drives one run to exactly one end (Leo §5.2 steps 6 to 11, AG-D12, AG-D14).

The run first makes sure it is still wanted and still holds its thread, then goes through the
frame — context, model, respond — within the turn's 180 s. Whatever happens it ends once: the
final transaction moves the run from `running` with a condition, so of the worker and the
sweep exactly one records the end, and only the one that recorded it writes the terminal
event. The answer is kept with the text the model wrote, even when stopped or failed midway;
the failure is never part of the text. A run that lost its lease writes nothing more: the
sweep has ended it. Every unexpected error ends the run `failed` and is logged with its stack.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import structlog

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.requests import ChatRequest
from shosai.core.ai.results import ChatDelta
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.features.agent.application.model_stream import (
    DEFAULT_PACE,
    AnswerBuffer,
    ModelStalledError,
    Pace,
    stream_answer,
)
from shosai.features.agent.application.run_context import (
    ContextBuilder,
    RunOverError,
    ThreadGoneError,
)
from shosai.features.agent.application.run_end import record_end
from shosai.features.agent.application.run_registry import ActiveRun, RunRegistry
from shosai.features.agent.application.turn_task import RunEmitter, TurnPayload
from shosai.features.agent.domain.endings import Ending, answered, cancelled, failed, stopped
from shosai.features.agent.domain.runs import TURN_DEADLINE, RunFailure
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.turn_graph import (
    ModelAnswer,
    TurnAnswer,
    TurnGraph,
    run_turn,
)

RUN = AgentRunRecord
log = structlog.stdlib.get_logger(__name__)


class ModelStreams(Protocol):
    """The provider port's streaming chat, as the engine uses it."""

    def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncIterator[ChatDelta]:
        """The model's answer as it is written."""
        ...


@dataclass(frozen=True, slots=True)
class EngineParts:
    """What the engine works with in an agent worker."""

    transactions: HomeTransactions
    ai: ModelStreams
    route: ModelRoute | None
    run_log: RunLog
    leases: ThreadLeases
    fleet: Fleet
    registry: RunRegistry
    outbox: EventOutbox
    graph: TurnGraph
    context: ContextBuilder
    pace: Pace = DEFAULT_PACE


class RunSteps:
    """The nodes' work for one run: read the conversation, call the model."""

    def __init__(
        self,
        parts: EngineParts,
        run: tuple[TurnPayload, ModelRoute],
        buffer: AnswerBuffer,
    ) -> None:
        self._parts = parts
        self._payload, self._route = run
        self._buffer = buffer

    async def context(self) -> ChatRequest:
        """The policy, the recent conversation and the question."""
        scope = self._payload.scope()
        async with self._parts.transactions.begin(scope, read_only=True) as session:
            return await self._parts.context.request(session, self._payload)

    async def model(self, request: ChatRequest) -> ModelAnswer:
        """The model's answer through the provider port, streamed as it is written."""
        payload = self._payload
        context = CallContext(
            effect_key=f"agent.turn:{payload.run_id}:1",
            feature="agent.turn",
            call_class=CallClass.STANDARD,
            origin=CallOrigin.INTERACTIVE,
            scope=payload.scope(),
            cross_border_consent=payload.cross_border_consent,
            deadline=TURN_DEADLINE,
        )
        deltas = self._parts.ai.stream_chat(context, self._route, request)
        return await stream_answer(deltas, self._buffer, self._parts.pace)


class RunEngine:
    """Drives the runs sent to this worker."""

    def __init__(
        self,
        parts: EngineParts,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._parts = parts
        self._clock = clock
        self._monotonic = monotonic

    async def run(self, payload: TurnPayload) -> None:
        """Drive the run to its one end."""
        user_id = payload.scope().user_id
        if user_id is None:
            message = "ход Leo идёт от имени человека"
            raise ValueError(message)
        run = ActiveRun(payload.run_id, payload.thread_id, user_id)
        emitter = RunEmitter(self._parts.run_log, payload.run_id)
        buffer = AnswerBuffer(emitter.text, self._monotonic())
        self._parts.registry.join(run)
        try:
            ending, answer = await self._drive(payload, run, buffer)
        except RunOverError:
            log.info("Ход Leo закончен до того, как его взял воркер")
            return
        # Ровно один конец: непредвиденная ошибка — это `failed` со стеком в журнале.
        except Exception:
            log.exception("Ход Leo упал")
            ending, answer = failed(RunFailure.FAILED), None
        finally:
            self._parts.registry.leave(run)
        if run.lost:
            log.warning("Ход Leo потерял аренду: конец записал обход")
            return
        await self._finish(payload, (ending, answer), buffer, emitter)

    async def _drive(
        self, payload: TurnPayload, run: ActiveRun, buffer: AnswerBuffer
    ) -> tuple[Ending, ModelAnswer | None]:
        route = self._parts.route
        if route is None:
            log.error("Ход Leo без модели: не задан AGENT_STANDARD_MODEL")
            return failed(RunFailure.MODEL_UNAVAILABLE), None
        early = await self._early_end(payload)
        if early is not None:
            return early, None
        steps = RunSteps(self._parts, (payload, route), buffer)
        work = asyncio.create_task(run_turn(self._parts.graph, steps), name="agent-turn")
        run.work = work
        return await self._outcome(payload, work)

    async def _early_end(self, payload: TurnPayload) -> Ending | None:
        """A run stopped before it began, or whose thread another run holds, ends stopped."""
        leases = self._parts.leases
        if payload.run_id in await leases.stops_asked([payload.run_id]):
            return stopped()
        lost = await leases.renew([(payload.thread_id, payload.run_id)])
        if lost and not await leases.take(payload.thread_id, payload.run_id):
            return stopped()
        return None

    async def _outcome(
        self, payload: TurnPayload, work: asyncio.Task[TurnAnswer]
    ) -> tuple[Ending, ModelAnswer | None]:
        """How the frame's work ended, within the turn's deadline."""
        remaining = (payload.started_at + TURN_DEADLINE - self._clock()).total_seconds()
        try:
            kept = await asyncio.wait_for(work, max(remaining, 0.0))
        except TimeoutError:
            return failed(RunFailure.TURN_DEADLINE), None
        except ModelStalledError, AiCallError:
            return failed(RunFailure.MODEL_UNAVAILABLE), None
        except ThreadGoneError:
            return cancelled(), None
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if work.cancelled() and current is not None and current.cancelling() == 0:
                return stopped(), None
            raise
        return answered(truncated=kept.truncated), kept.model

    async def _finish(
        self,
        payload: TurnPayload,
        result: tuple[Ending, ModelAnswer | None],
        buffer: AnswerBuffer,
        emitter: RunEmitter,
    ) -> None:
        ending, answer = result
        try:
            recorded = await record_end(
                (self._parts.transactions, self._parts.outbox),
                payload,
                (ending, buffer.text, answer),
                self._clock(),
            )
            if recorded is not None:
                await emitter.emit(*recorded.terminal(payload.reply_id))
        except REDIS_FAILURES as error:
            # Конец записан в базе; поток клиента возьмёт его оттуда, если журнал недоступен.
            log.warning("Конец хода Leo не попал в журнал", error_type=type(error).__name__)
        finally:
            await self._release(payload)

    async def _release(self, payload: TurnPayload) -> None:
        user_id = payload.scope().user_id
        try:
            await self._parts.leases.release(payload.thread_id, payload.run_id)
            if user_id is not None:
                await self._parts.fleet.release(user_id, payload.run_id)
        except REDIS_FAILURES as error:
            # Аренда и счёт истекут сами через 30 с.
            log.warning("Аренда хода Leo не снята", error_type=type(error).__name__)
