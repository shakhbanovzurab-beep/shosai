"""The meetings' sweeps: the forgotten ones ended, the ended ones settled (MT-D2, inv-6, inv-7).

Every minute per home, the live sweep ends an active meeting 5 minutes after its last
audio as capture reports it (its last line until capture binds the port), and every
meeting at 6 hours. The settle sweep takes each meeting ended at least a minute ago and not
settled: it compares the stored live lines with the highest line capture showed (inv-6),
counts the lines and gives a spoken live meeting its run if its end found no speech yet —
the drain may store the last lines after the client's end (inv-7). The sweep role only
lists what is due; each meeting is ended or settled in its owner's transaction, and no
transaction is open while capture is asked.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import func, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.notes.application.lifecycle import MeetingLifecycle
from shosai.features.notes.application.run_rows import ensure_run
from shosai.features.notes.application.transcript_stats import live_seqs_up_to, spoken
from shosai.features.notes.contracts import LIVE_SIGNAL, LiveSignal
from shosai.features.notes.domain.meetings import (
    SILENCE_AFTER,
    MeetingClock,
    MeetingSource,
    MeetingStatus,
    sweep_cause,
    sweep_end,
)
from shosai.features.notes.domain.runs import RunSource, idempotency_key
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.transcript_metrics import TranscriptMetrics

BATCH: Final = 500
SETTLE_GRACE: Final = timedelta(minutes=1)
# Дольше этого закончившаяся встреча без досчёта — сигнал, что обход не справляется (inv-7).
UNSETTLED_AFTER: Final = timedelta(minutes=15)
log = structlog.stdlib.get_logger(__name__)


class MeetingSweeps:
    """The live and the settle sweeps of one process."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, MeetingLifecycle, TranscriptMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._lifecycle, self._metrics = collaborators
        self._clock = clock

    def _signal(self) -> LiveSignal | None:
        bound = self._ports.all(LIVE_SIGNAL)
        return bound[0] if bound else None

    async def end_forgotten(self, home: Home) -> int:
        """End the home's meetings silent for 5 minutes or 6 hours long; how many ended."""
        now = self._clock()
        last_line = (
            select(func.max(TranscriptLineRecord.start_ms + TranscriptLineRecord.duration_ms))
            .where(
                TranscriptLineRecord.session_id == MeetingRecord.id,
                TranscriptLineRecord.meeting_started_at == MeetingRecord.started_at,
            )
            .correlate(MeetingRecord)
            .scalar_subquery()
        )
        due = (
            select(MeetingRecord.id, MeetingRecord.user_id, MeetingRecord.org_id)
            .add_columns(MeetingRecord.started_at, last_line)
            .where(
                MeetingRecord.status == MeetingStatus.ACTIVE.value,
                MeetingRecord.deleted_at.is_(None),
                MeetingRecord.started_at <= now - SILENCE_AFTER,
            )
            .order_by(MeetingRecord.started_at)
            .limit(BATCH)
        )
        async with self._transactions.begin(TenancyScope(home), read_only=True, sweep=True) as s:
            rows = (await s.execute(due)).all()
        signal = self._signal()
        audio: Mapping[UUID, datetime] = (
            await signal.last_audio([row[0] for row in rows]) if signal and rows else {}
        )
        ended = 0
        for meeting_id, user_id, org_id, started_at, last_end_ms in rows:
            last_line_end = (
                None if last_end_ms is None else started_at + timedelta(milliseconds=last_end_ms)
            )
            clock = MeetingClock(started_at, last_line_end=last_line_end)
            ending = sweep_end(clock, audio.get(meeting_id), now)
            cause = sweep_cause(clock, audio.get(meeting_id), now)
            if ending is None or cause is None:
                continue
            scope = TenancyScope(home, user_id, org_id)
            ended += await self._lifecycle.close_swept(scope, meeting_id, cause, ending.ended_at)
        if ended:
            log.info("Забытые встречи закрыты", home=home.value, meetings=ended)
        return ended

    async def settle(self, home: Home) -> int:
        """Settle the home's meetings ended a minute ago or more; how many were settled."""
        now = self._clock()
        unsettled = (
            MeetingRecord.status != MeetingStatus.ACTIVE.value,
            MeetingRecord.settled_at.is_(None),
            MeetingRecord.deleted_at.is_(None),
        )
        due = (
            select(MeetingRecord.id, MeetingRecord.user_id, MeetingRecord.org_id)
            .where(*unsettled, MeetingRecord.ended_at <= now - SETTLE_GRACE)
            .order_by(MeetingRecord.ended_at)
            .limit(BATCH)
        )
        late = select(func.count()).where(
            *unsettled, MeetingRecord.ended_at <= now - UNSETTLED_AFTER
        )
        async with self._transactions.begin(TenancyScope(home), read_only=True, sweep=True) as s:
            rows = (await s.execute(due)).all()
        signal = self._signal()
        for meeting_id, user_id, org_id in rows:
            shown = await signal.highest_shown(meeting_id) if signal else None
            await self._settle_one(TenancyScope(home, user_id, org_id), meeting_id, shown)
        async with self._transactions.begin(TenancyScope(home), read_only=True, sweep=True) as s:
            self._metrics.unsettled(home, int(await s.scalar(late) or 0))
        return len(rows)

    async def _settle_one(self, scope: TenancyScope, meeting_id: UUID, shown: int | None) -> None:
        started = await self._settled(scope, meeting_id, shown)
        if started is not None:
            await self._lifecycle.start_run(scope, started, None)

    async def _settled(
        self, scope: TenancyScope, meeting_id: UUID, shown: int | None
    ) -> UUID | None:
        """Settle one meeting in its owner's transaction; the run it started, if any."""
        started = None
        async with self._transactions.begin(scope) as session:
            record = await session.scalar(
                select(MeetingRecord)
                .where(MeetingRecord.id == meeting_id, MeetingRecord.settled_at.is_(None))
                .with_for_update()
            )
            if record is None:
                return None
            lines, _ = await spoken(session, record)
            if shown:
                missing = shown - await live_seqs_up_to(session, record, shown)
                fresh = missing - record.lines_missing
                if fresh > 0:
                    self._metrics.missing(fresh)
                    record.lines_missing = missing
                    log.error(
                        "Показанные строки не сохранены", meeting_id=str(meeting_id), lines=fresh
                    )
            record.line_count = lines
            live = record.source == MeetingSource.LIVE.value
            if record.kept and live and lines > 0:
                run_id = await ensure_run(
                    session, record, RunSource.LIVE, idempotency_key(RunSource.LIVE)
                )
                if record.latest_run_id is None:
                    log.info("Встрече без прогона заведён прогон", meeting_id=str(meeting_id))
                    record.latest_run_id = started = run_id
            record.settled_at = self._clock()
        return started
