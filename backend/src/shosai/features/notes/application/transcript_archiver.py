"""The transcript archive's pass: old months' meetings to the bucket, then their partition.

A pass takes the oldest partition of a month that ended 12 months ago or earlier. The sweep
role lists a batch of its meetings still without an archive; each meeting's lines are read
in its own scope, put in the home's bucket, read back and compared by digest, and only then
does the meeting get its pointer — in a transaction that locks it and counts its lines again,
so a line that arrived meanwhile sends it to the next pass; a meeting deleted meanwhile has
its object removed. No line arrives after that: the drain takes none for a meeting started
more than 12 months ago (`meetings_live_facts`), and the align stage none for an archived
one. Storage is never called inside a transaction (§14 rule 8). When no meeting of the month
is left, the owner's function drops the partition after checking that itself. A repeated
pass writes the same object again (plan step 20).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import Select, func, select, text

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.domain.transcript_archive import (
    archive_key,
    encode_lines,
    last_month_due,
    lines_digest,
)
from shosai.features.notes.infrastructure.archive_metrics import ArchiveMetrics, ArchiveOutcome
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.transcript_archive import (
    PartitionDrop,
    TranscriptArchive,
    drop_archived_month,
)
from shosai.features.notes.infrastructure.transcript_rows import stored_lines

BATCH: Final = 100
DECEMBER: Final = 12
PARTITION: Final = re.compile(r"transcript_segments_p(\d{4})(\d{2})")
PARTITIONS: Final = text(
    "SELECT c.relname FROM pg_inherits AS i JOIN pg_class AS c ON c.oid = i.inhrelid "
    "WHERE i.inhparent = 'public.transcript_segments'::regclass"
)
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Due:
    """A meeting of the month to archive, with the scope its lines are read in."""

    meeting_id: UUID
    user_id: UUID
    org_id: UUID | None


def unarchived(start: datetime, end: datetime) -> Select[UUID, UUID, UUID | None]:
    """The month's meetings without an archive, oldest first."""
    return (
        select(MeetingRecord.id, MeetingRecord.user_id, MeetingRecord.org_id)
        .where(
            MeetingRecord.started_at >= start,
            MeetingRecord.started_at < end,
            MeetingRecord.transcript_archive_key.is_(None),
        )
        .order_by(MeetingRecord.started_at)
    )


def next_month(month: date) -> date:
    """The first day of the following month."""
    if month.month == DECEMBER:
        return date(month.year + 1, 1, 1)
    return month.replace(month=month.month + 1)


class TranscriptArchiver:
    """Moves old months' transcripts to the bucket and drops their partitions."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[TranscriptArchive, ArchiveMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._archive, self._metrics = collaborators
        self._clock = clock

    async def run(self, home: Home) -> int:
        """One pass over the oldest due month; how many meetings were archived."""
        month = await self._oldest_due(home)
        if month is None:
            return 0
        following = next_month(month)
        start = datetime(month.year, month.month, 1, tzinfo=UTC)
        end = datetime(following.year, following.month, 1, tzinfo=UTC)
        meetings = await self._listed(home, unarchived(start, end))
        archived = 0
        for due in meetings:
            scope = TenancyScope(home, due.user_id, due.org_id)
            archived += await self._archived(scope, due.meeting_id)
        # Последняя порция месяца: партицию проверит и удалит функция владельца.
        if len(meetings) < BATCH:
            await self._dropped(home, month)
        return archived

    async def _listed(self, home: Home, query: Select[UUID, UUID, UUID | None]) -> list[Due]:
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rows = (await session.execute(query.limit(BATCH))).all()
        return [Due(meeting_id, user_id, org_id) for meeting_id, user_id, org_id in rows]

    async def _oldest_due(self, home: Home) -> date | None:
        last = last_month_due(self._clock())
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            names = (await session.scalars(PARTITIONS)).all()
        months = sorted(
            date(int(found[1]), int(found[2]), 1)
            for name in names
            if (found := PARTITION.fullmatch(name)) is not None
        )
        due = [month for month in months if month <= last]
        return due[0] if due else None

    async def _archived(self, scope: TenancyScope, meeting_id: UUID) -> int:
        lines = await stored_lines(self._transactions, scope, meeting_id)
        data = encode_lines(lines)
        key = archive_key(meeting_id)
        await self._archive.put(scope.home, key, data)
        if lines_digest(await self._archive.raw(scope.home, key)) != lines_digest(data):
            return self._refused(scope.home, meeting_id, "архив не совпал со строками")
        count: int | None = None
        async with self._transactions.begin(scope) as session:
            meeting = await session.get(MeetingRecord, meeting_id, with_for_update=True)
            if meeting is not None:
                count = await session.scalar(
                    select(func.count()).where(
                        TranscriptLineRecord.session_id == meeting_id,
                        TranscriptLineRecord.meeting_started_at == meeting.started_at,
                    )
                )
                if count == len(lines):
                    meeting.transcript_archive_key = key
                    meeting.transcript_archive_lines = len(lines)
        if meeting is None:
            # Встречу стёрли, пока шёл архив: её объект никому не нужен.
            await self._archive.delete(scope.home, key)
            return 0
        if count != len(lines):
            return self._refused(scope.home, meeting_id, "пока шёл архив, пришли строки")
        self._metrics.archived(scope.home, ArchiveOutcome.ARCHIVED)
        return 1

    def _refused(self, home: Home, meeting_id: UUID, reason: str) -> int:
        self._metrics.archived(home, ArchiveOutcome.MISMATCH)
        log.warning("Расшифровка не ушла в архив", meeting_id=str(meeting_id), reason=reason)
        return 0

    async def _dropped(self, home: Home, month: date) -> None:
        async with self._transactions.begin(TenancyScope(home), sweep=True) as session:
            outcome = await drop_archived_month(session, month)
        if outcome is PartitionDrop.DROPPED:
            self._metrics.dropped(home)
            log.info(
                "Партиция расшифровок удалена после архива", home=home.value, month=f"{month:%Y-%m}"
            )
