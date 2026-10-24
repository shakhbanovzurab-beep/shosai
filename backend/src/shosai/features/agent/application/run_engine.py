"""An agent worker drives one run to exactly one end (Leo §5.2 steps 6 to 11, AG-D12, AG-D14).

The run first makes sure it is still wanted and still holds its thread, then goes through the
frame — context, the model's rounds and the tools between them, respond — within the turn's
180 s. Whatever happens it ends once: the
final transaction moves the run from `running` with a condition, so of the worker and the
sweep exactly one records the end, and only the one that recorded it writes the terminal
event. The answer is kept with the text the model wrote and the steps it took, even when
stopped or failed midway; the failure is never part of the text. A run that lost its lease
writes nothing more: the sweep has ended it. Every unexpected error ends the run `failed` and
is logged with its stack.
"""

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime

import structlog

from shosai.core.ai.errors import AiCallError
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.features.agent.application.model_stream import AnswerBuffer, ModelStalledError
from shosai.features.agent.application.run_context import RunOverError, ThreadGoneError
from shosai.features.agent.application.run_end import record_end
from shosai.features.agent.application.run_engine_parts import EngineParts
from shosai.features.agent.application.run_registry import ActiveRun
from shosai.features.agent.application.run_steps import RunState, RunSteps
from shosai.features.agent.application.run_telemetry import TurnTimes
from shosai.features.agent.application.run_work import RunWork
from shosai.features.agent.application.turn_task import RunEmitter, TurnPayload
from shosai.features.agent.domain.endings import Ending, answered, cancelled, failed, stopped
from shosai.features.agent.domain.runs import TURN_DEADLINE, RunFailure
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.turn_graph import TurnAnswer, run_turn

RUN = AgentRunRecord
log = structlog.stdlib.get_logger(__name__)


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
        state = RunState(
            payload, self._parts.route, TurnTimes(picked_up=self._clock()),
            AnswerBuffer(emitter.text, self._monotonic()), RunWork(), emitter,
        )  # fmt: skip
        telemetry, registry = self._parts.telemetry, self._parts.registry
        telemetry.picked(payload, state.times)
        with telemetry.run(payload):
            registry.join(run)
            telemetry.metrics.active(registry.count)
            try:
                ending = await self._drive(state, run)
            except RunOverError:
                log.info("Ход Leo закончен до того, как его взял воркер")
                return
            # Ровно один конец: непредвиденная ошибка — это `failed` со стеком в журнале.
            except Exception:
                log.exception("Ход Leo упал")
                ending = failed(RunFailure.FAILED)
            finally:
                registry.leave(run)
                telemetry.metrics.active(registry.count)
            if run.lost:
                log.warning("Ход Leo потерял аренду: конец записал обход")
                return
            await self._finish(state, ending)

    async def _drive(self, state: RunState, run: ActiveRun) -> Ending:
        if state.route is None:
            log.error("Ход Leo без модели: не задан AGENT_STANDARD_MODEL")
            return failed(RunFailure.MODEL_UNAVAILABLE)
        early = await self._early_end(state.payload)
        if early is not None:
            return early
        steps = RunSteps(self._parts, state, self._monotonic)
        work = asyncio.create_task(run_turn(self._parts.graph, steps), name="agent-turn")
        run.work = work
        return await self._outcome(state.payload, work)

    async def _early_end(self, payload: TurnPayload) -> Ending | None:
        """A run stopped before it began, or whose thread another run holds, ends stopped."""
        leases = self._parts.leases
        if payload.run_id in await leases.stops_asked([payload.run_id]):
            return stopped()
        lost = await leases.renew([(payload.thread_id, payload.run_id)])
        if lost and not await leases.take(payload.thread_id, payload.run_id):
            return stopped()
        return None

    async def _outcome(self, payload: TurnPayload, work: asyncio.Task[TurnAnswer]) -> Ending:
        """How the frame's work ended, within the turn's deadline."""
        remaining = (payload.started_at + TURN_DEADLINE - self._clock()).total_seconds()
        try:
            kept = await asyncio.wait_for(work, max(remaining, 0.0))
        except TimeoutError:
            return failed(RunFailure.TURN_DEADLINE)
        except ModelStalledError, AiCallError:
            return failed(RunFailure.MODEL_UNAVAILABLE)
        except ThreadGoneError:
            return cancelled()
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if work.cancelled() and current is not None and current.cancelling() == 0:
                return stopped()
            raise
        return answered(truncated=kept.truncated)

    async def _finish(self, state: RunState, ending: Ending) -> None:
        payload, times = state.payload, state.times
        text = state.buffer.text
        answer = state.work.total(text)
        now = self._clock()
        try:
            recorded = await record_end(
                (self._parts.transactions, self._parts.outbox),
                payload,
                (ending, text, answer),
                (times, now),
                state.work,
            )
            if recorded is not None:
                self._parts.telemetry.ended(payload, (recorded, answer), times, now)
                await state.emitter.emit(*recorded.terminal(payload.reply_id))
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
