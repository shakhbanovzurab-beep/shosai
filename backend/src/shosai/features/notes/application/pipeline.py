"""The post-meeting pipeline's engine (§8.1 Pipeline run, §11.3, §14 rules 1 and 6).

A delivery of a stage takes the run's row lock, decides whether the stage runs (`claim`),
marks it running with one more attempt and commits — the mark is durable before any
provider is called (the draft paid twice when it only flushed it, 2850807d7). The stage's
handler then works without an open transaction of the engine, in its own short ones. A
second transaction records the outcome: done, given back for another attempt, or failed;
a critical failure fails the run, a non-critical one lets it go on, partially completed.
The next stage's task is sent only after that commit; if the send fails, the recovery
sweep sends it. A stage whose handler this process does not have waits for one.
"""

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Protocol
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.errors import AiCallError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.features.notes.application.run_rows import progress_of, stage_state
from shosai.features.notes.application.stage_task import RUN_STAGE, StagePayload, StageRetryError
from shosai.features.notes.domain.runs import (
    TERMINAL,
    Claim,
    GiveUp,
    RunSource,
    RunState,
    Stage,
    StageRecord,
    StageStatus,
    after_failure,
    claim,
    next_stage,
    outcome,
)
from shosai.features.notes.infrastructure.pipeline_metrics import PipelineMetrics
from shosai.features.notes.infrastructure.run_records import RunRecord

INTERNAL_ERROR: Final = "internal_error"
ATTEMPTS_EXHAUSTED: Final = "attempts_exhausted"
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class StageWork:
    """What a stage's handler is given: the run, its meeting, its source and the attempt."""

    scope: TenancyScope
    run_id: UUID
    meeting_id: UUID
    source: RunSource
    stage: Stage
    attempt: int


class StageFailedError(Exception):
    """A stage's failure with its code; retried unless the code says retrying cannot help."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class StageSender(Protocol):
    """Queues a stage's task: the process's `TaskSender`."""

    async def send(self, task: TaskDeclaration[StagePayload], payload: StagePayload) -> str:
        """Queue the task; `TaskQueueUnavailableError` when the queue does not answer."""
        ...


class StageHandler(Protocol):
    """One stage's work; it opens its own transactions and never holds one across a call out."""

    async def run(self, work: StageWork) -> None:
        """Do the stage; raise `StageFailedError` with a code when it fails."""
        ...


@dataclass(frozen=True, slots=True)
class _Finished:
    next: Stage | None
    retry: bool


NOTHING: Final = _Finished(None, retry=False)


class PipelineEngine:
    """Runs the stages of runs and starts new runs."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[StageSender, PipelineMetrics, Mapping[Stage, StageHandler]],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._sender, self._metrics, self._handlers = collaborators
        self._clock = clock

    def handles(self, stage: Stage) -> bool:
        """Whether this process can run the stage."""
        return stage in self._handlers

    async def kick(self, scope: TenancyScope, run_id: UUID, stage: Stage) -> None:
        """Send a stage's task after its run's commit; a failed send waits for the sweep."""
        try:
            await self._send(scope, run_id, stage)
        except TaskQueueUnavailableError:
            log.warning("Стадия прогона не поставлена: её отправит обход", run_id=str(run_id))

    async def run_stage(self, payload: StagePayload) -> None:
        """One delivery of a stage: claim, work outside a transaction, record, send the next."""
        work = await self._claim(payload)
        if isinstance(work, _Finished):
            if work.next is not None:
                await self._send(payload.scope(), payload.run_id, work.next)
            return
        started, code = time.monotonic(), None
        try:
            await self._handlers[payload.stage].run(work)
        except StageFailedError as failure:
            code = failure.code
        except AiCallError as failure:
            code = failure.failure.value
        except Exception:
            # Любой сбой стадии записывается её кодом: не теряется и не роняет доставку.
            log.exception(
                "Стадия прогона упала", run_id=str(payload.run_id), stage=payload.stage.value
            )
            code = INTERNAL_ERROR
        finished = await self._finish(payload, code)
        outcome_label = "done" if code is None else ("retry" if finished.retry else "failed")
        self._metrics.attempt(payload.stage, outcome_label, time.monotonic() - started)
        if finished.next is not None:
            await self._send(payload.scope(), payload.run_id, finished.next)
        if finished.retry:
            raise StageRetryError(code)

    async def _send(self, scope: TenancyScope, run_id: UUID, stage: Stage) -> None:
        payload = StagePayload(
            home=scope.home, user_id=scope.user_id, org_id=scope.org_id, run_id=run_id, stage=stage
        )
        await self._sender.send(RUN_STAGE, payload)

    async def _locked(self, session: AsyncSession, run_id: UUID) -> RunRecord | None:
        return await session.scalar(
            select(RunRecord).where(RunRecord.id == run_id).with_for_update()
        )

    async def _claim(self, payload: StagePayload) -> StageWork | _Finished:
        """The stage's work, or what is left to do when the delivery runs nothing."""
        now = self._clock()
        async with self._transactions.begin(payload.scope()) as session:
            run = await self._locked(session, payload.run_id)
            if run is None or RunState(run.state) in TERMINAL:
                return NOTHING
            source, progress = RunSource(run.source), progress_of(run.stage_state)
            if next_stage(source, progress) is not payload.stage or not self.handles(payload.stage):
                return NOTHING
            record = progress.get(payload.stage, StageRecord())
            stale = (now - run.updated_at) > RUN_STAGE.hold_limit
            decision = claim(record, stale=stale)
            if decision is Claim.EXHAUSTED:
                progress[payload.stage] = StageRecord(
                    StageStatus.FAILED, record.attempts, ATTEMPTS_EXHAUSTED
                )
                ended = self._settle(run, source, progress, now)
                return _Finished(None if ended else next_stage(source, progress), retry=False)
            if decision is not Claim.RUN:
                return NOTHING
            attempt = record.attempts + 1
            progress[payload.stage] = StageRecord(StageStatus.RUNNING, attempt, record.error_code)
            run.state, run.stage_state, run.updated_at = (
                RunState.RUNNING.value,
                stage_state(progress),
                now,
            )
            return StageWork(
                payload.scope(), run.id, run.session_id, source, payload.stage, attempt
            )

    async def _finish(self, payload: StagePayload, code: str | None) -> _Finished:
        now = self._clock()
        async with self._transactions.begin(payload.scope()) as session:
            run = await self._locked(session, payload.run_id)
            if run is None or RunState(run.state) in TERMINAL:
                return NOTHING
            source, progress = RunSource(run.source), progress_of(run.stage_state)
            record = progress.get(payload.stage, StageRecord())
            if record.status is not StageStatus.RUNNING:
                return NOTHING
            retry = False
            if code is None:
                progress[payload.stage] = StageRecord(StageStatus.DONE, record.attempts)
            elif isinstance(after_failure(record.attempts, code), GiveUp):
                progress[payload.stage] = StageRecord(StageStatus.FAILED, record.attempts, code)
                log.warning(
                    "Стадия прогона провалена",
                    run_id=str(run.id),
                    stage=payload.stage.value,
                    code=code,
                )
            else:
                progress[payload.stage] = StageRecord(StageStatus.PENDING, record.attempts, code)
                retry = True
            ended = self._settle(run, source, progress, now)
            nxt = None if retry or ended else next_stage(source, progress)
            return _Finished(nxt, retry)

    def _settle(
        self,
        run: RunRecord,
        source: RunSource,
        progress: Mapping[Stage, StageRecord],
        now: datetime,
    ) -> bool:
        """Write the stages and, when the run is over, its end; whether it ended."""
        run.stage_state, run.updated_at = stage_state(dict(progress)), now
        state = outcome(source, progress)
        if state is None:
            return False
        run.state, run.finished_at = state.value, now
        failed = [r.error_code for r in progress.values() if r.status is StageStatus.FAILED]
        run.error_code = failed[0] if failed else None
        self._metrics.finished(source, state, (now - run.created_at).total_seconds())
        log.info("Прогон закончился", run_id=str(run.id), state=state.value)
        return True
