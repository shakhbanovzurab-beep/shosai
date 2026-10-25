"""A paused run taken back for its epilogue once its card's action ended (Leo §5.3; step 9a2).

The decider hands the run to the `agent` queue. A worker there takes it back only while the
frame still keeps it paused, its log is alive, the thread's lease is free — a new turn on the
thread holds it, and closes the paused run itself — and the run row moves from `paused` to
`running` with a condition, so of two deliveries one goes on. Anything short of that ends the
run without its epilogue: the action lives in the database, and its server note already tells
the thread what became of it. The resume is the admitted turn going on, so it is not counted
against the person's two runs again; the `agent` queue's own concurrency bounds it.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

import structlog
from pydantic import ValidationError
from sqlalchemy import update

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.runs import RunStatus
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_metrics import RunMetrics
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.turn_graph import TurnGraph, paused_terms
from shosai.features.agent.infrastructure.turn_saver import TurnSaver

RUN = AgentRunRecord
log = structlog.stdlib.get_logger(__name__)


class ResumePayload(HomeTaskPayload):
    """A paused run whose card's action ended: the run, its thread and the action."""

    run_id: UUID
    thread_id: UUID
    action_id: UUID


RESUME_RUN: Final = TaskDeclaration(
    name="agent.resume_run",
    queue=TaskQueue.AGENT,
    payload=ResumePayload,
    deadline=timedelta(seconds=200),
    retry=NO_RETRY,
)


class ResumeOutcome(StrEnum):
    """What became of a hand-over: the epilogue began, the frame was gone, or the run had
    already ended — a new turn closed it, or another delivery took it."""

    RESUMED = "resumed"
    CHECKPOINT_LOST = "checkpoint_lost"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class Resumed:
    """A run taken back: its terms, the action decided, and its log's last event."""

    payload: TurnPayload
    action_id: UUID
    after: int


class RunResumption:
    """Takes paused runs back for their epilogues."""

    def __init__(
        self,
        transactions: HomeTransactions,
        frame: tuple[TurnGraph, TurnSaver, RunLog, ThreadLeases],
        metrics: RunMetrics,
    ) -> None:
        self._transactions = transactions
        self._graph, self._frames, self._log, self._leases = frame
        self._metrics = metrics

    async def claim(self, resume: ResumePayload) -> Resumed | ResumeOutcome:
        """The run, taken back for its epilogue; or why it cannot be."""
        found = await self._kept(resume)
        if found is None:
            return self._counted(ResumeOutcome.CHECKPOINT_LOST)
        payload, after = found
        if not await self._leases.take(payload.thread_id, payload.run_id):
            return self._counted(ResumeOutcome.CLOSED)
        async with self._transactions.begin(payload.scope()) as session:
            won = await session.scalar(
                update(RUN)
                .where(
                    RUN.id == payload.run_id,
                    RUN.user_id == payload.user_id,
                    RUN.status == RunStatus.PAUSED.value,
                )
                .values(status=RunStatus.RUNNING.value)
                .returning(RUN.id)
            )
        if won is None:
            await self._leases.release(payload.thread_id, payload.run_id)
            await self._frames.forget(payload.run_id)
            return self._counted(ResumeOutcome.CLOSED)
        self._metrics.resumed_run(ResumeOutcome.RESUMED.value)
        return Resumed(payload, resume.action_id, after)

    async def _kept(self, resume: ResumePayload) -> tuple[TurnPayload, int] | None:
        """The paused turn's terms and its log's last event, while both are kept."""
        try:
            terms = await paused_terms(self._graph, resume.run_id)
            last = await self._log.last(resume.run_id)
        except REDIS_FAILURES as error:
            log.warning("Кадр хода Leo не прочитан", error_type=type(error).__name__)
            return None
        if terms is None or last is None:
            return None
        try:
            payload = TurnPayload.model_validate(terms)
        except ValidationError:
            log.exception("Условия хода Leo в кадре не читаются", run=resume.run_id)
            return None
        same = (payload.run_id, payload.user_id, payload.home)
        if same != (resume.run_id, resume.user_id, resume.home):
            log.error("Кадр хода Leo не совпал с передачей", run=resume.run_id)
            return None
        return payload, last.seq

    def _counted(self, outcome: ResumeOutcome) -> ResumeOutcome:
        self._metrics.resumed_run(outcome.value)
        return outcome
