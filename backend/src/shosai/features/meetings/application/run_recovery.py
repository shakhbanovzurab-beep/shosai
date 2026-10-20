"""The recovery of runs from the database (§8.1 "the queue may be lost, the sweep restores", §13.3).

Every minute per home the sweep finds unfinished runs whose stage's task seems lost: a run
never started three minutes after its creation (longer than the broker's longest back-off),
a stage given back for another attempt and not delivered since, or a stage running longer
than a worker may hold it — its worker died. It sends that stage's task again; the claim
under the run's lock keeps a duplicate delivery from running the stage twice, and the
attempts in the row keep any path within three. It also reports the age of the oldest
unfinished run. A desktop recording's run waits, passed by and not counted, until its audio
is bound and its meeting has ended; then the sweep starts it (MT-D3). The sweep role only
lists; the send needs no transaction.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final

import structlog
from sqlalchemy import ColumnElement, and_, or_, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.application.pipeline import PipelineEngine
from shosai.features.meetings.application.run_rows import progress_of
from shosai.features.meetings.application.stage_task import RUN_STAGE
from shosai.features.meetings.domain.meetings import MeetingStatus
from shosai.features.meetings.domain.runs import (
    RunSource,
    RunState,
    StageRecord,
    StageStatus,
    next_stage,
)
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.pipeline_metrics import PipelineMetrics
from shosai.features.meetings.infrastructure.run_records import RunRecord

BATCH: Final = 200
# Сколько незаконченных прогонов читает расчёт самого старого: в пике их около 300 (§3).
OPEN_LIMIT: Final = 2000
# Дольше самой длинной паузы брокера между выдачами (120 с): задача стадии, видимо, потеряна.
LOST_AFTER: Final = timedelta(minutes=3)
OPEN: Final = (RunState.PENDING.value, RunState.RUNNING.value)
log = structlog.stdlib.get_logger(__name__)


def waiting_for_recording() -> ColumnElement[bool]:
    """A desktop recording's run whose audio is not bound yet or whose meeting goes on."""
    live = (
        select(MeetingRecord.id)
        .where(
            MeetingRecord.id == RunRecord.session_id,
            MeetingRecord.status == MeetingStatus.ACTIVE.value,
        )
        .exists()
    )
    return and_(
        RunRecord.source == RunSource.RECORDING.value,
        or_(RunRecord.audio_expires_at.is_(None), live),
    )


class RunRecovery:
    """Sends again the stages whose tasks are lost, and measures the oldest open run."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PipelineEngine, PipelineMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._engine, self._metrics = collaborators
        self._clock = clock

    async def run(self, home: Home) -> int:
        """One pass over the home; how many stages were sent again."""
        now = self._clock()
        stalled = (
            select(RunRecord)
            .where(
                RunRecord.state.in_(OPEN),
                RunRecord.updated_at <= now - LOST_AFTER,
                ~waiting_for_recording(),
            )
            .order_by(RunRecord.updated_at)
            .limit(BATCH)
        )
        open_runs = (
            select(RunRecord.created_at, RunRecord.source, RunRecord.stage_state)
            .where(RunRecord.state.in_(OPEN), ~waiting_for_recording())
            .order_by(RunRecord.created_at)
            .limit(OPEN_LIMIT)
        )
        async with self._transactions.begin(TenancyScope(home), read_only=True, sweep=True) as s:
            runs = (await s.scalars(stalled)).all()
            waiting = (await s.execute(open_runs)).all()
        # Прогон, чью стадию этот образ ещё не умеет, ждёт новой версии, а не обхода.
        workable = [
            created
            for created, source, state in waiting
            if (stage := next_stage(RunSource(source), progress_of(state))) is not None
            and self._engine.handles(stage)
        ]
        self._metrics.oldest_open(home, (now - workable[0]).total_seconds() if workable else 0.0)
        sent = 0
        for run in runs:
            progress = progress_of(run.stage_state)
            stage = next_stage(RunSource(run.source), progress)
            if stage is None or not self._engine.handles(stage):
                continue
            # Идущая стадия чужого живого воркера ещё в его аренде: её не трогаем.
            held = progress.get(stage, StageRecord()).status is StageStatus.RUNNING
            if held and now - run.updated_at <= RUN_STAGE.hold_limit:
                continue
            await self._engine.kick(TenancyScope(home, run.user_id, run.org_id), run.id, stage)
            sent += 1
        if sent:
            log.info("Стадии прогонов отправлены заново", home=home.value, stages=sent)
        return sent
