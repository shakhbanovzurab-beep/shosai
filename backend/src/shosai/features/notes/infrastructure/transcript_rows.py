"""A person's transcript lines, meeting by meeting: for export, copy and digest (§14 rule 1).

The transcript has no person column — five million lines a day would pay an index for it —
so a person's lines are reached through their meetings, each meeting's lines paged by
`seq` in their own short transactions: no transaction stays open while an archive goes to
storage or across both homes, and no meeting sits whole in memory. An archived meeting's
lines come from its object instead, read after no transaction, in the same form (step 20).
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import Table, select, update
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.person_rows import PAGE_ROWS, json_lines
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.domain.transcript_archive import (
    ArchivedLine,
    archive_key,
    encode_lines,
)
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.transcript_archive import TranscriptArchive

LINES: Final = cast("Table", TranscriptLineRecord.__table__)
# Выгружаются без служебного ключа партиции: он — копия начала встречи.
EXPORTED: Final = (
    "session_id", "seq", "started_at", "start_ms", "duration_ms", "speaker_idx", "text", "origin",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class PersonMeeting:
    """A person's own meeting as their transcript is reached: in its partition or archived."""

    id: UUID
    started_at: datetime
    # Ключ объекта архива и число строк в нём; None — строки в партиции.
    archive: tuple[str, int] | None


async def person_meetings(
    transactions: HomeTransactions, scope: TenancyScope, user_id: UUID
) -> list[PersonMeeting]:
    """The person's own meetings in the scope's home, not a workspace's, by id."""
    found: list[PersonMeeting] = []
    columns = (
        MeetingRecord.id, MeetingRecord.started_at,
        MeetingRecord.transcript_archive_key, MeetingRecord.transcript_archive_lines,
    )  # fmt: skip
    last: UUID | None = None
    while True:
        query = select(*columns).where(
            MeetingRecord.user_id == user_id, MeetingRecord.org_id.is_(None)
        )
        if last is not None:
            query = query.where(MeetingRecord.id > last)
        async with transactions.begin(scope, read_only=True) as session:
            rows = (await session.execute(query.order_by(MeetingRecord.id).limit(PAGE_ROWS))).all()
        found.extend(
            PersonMeeting(meeting_id, started, None if key is None else (key, lines or 0))
            for meeting_id, started, key, lines in rows
        )
        if len(rows) < PAGE_ROWS:
            return found
        last = found[-1].id


async def _pages(
    transactions: HomeTransactions,
    scope: TenancyScope,
    meeting_id: UUID,
    columns: Sequence[str],
) -> AsyncIterator[list[dict[str, Any]]]:
    table = LINES
    last = 0
    while True:
        query = select(*(table.c[name] for name in columns)).where(
            table.c.session_id == meeting_id, table.c.seq > last
        )
        async with transactions.begin(scope, read_only=True) as session:
            page = (await session.execute(query.order_by(table.c.seq).limit(PAGE_ROWS))).mappings()
            rows = [dict(row) for row in page.all()]
        if not rows:
            return
        yield rows
        if len(rows) < PAGE_ROWS:
            return
        last = rows[-1]["seq"]


ARCHIVED_COLUMNS: Final = (
    "seq", "started_at", "start_ms", "duration_ms", "speaker_idx", "text", "origin", "run_id",
    "created_at",
)  # fmt: skip


async def stored_lines(
    transactions: HomeTransactions, scope: TenancyScope, meeting_id: UUID
) -> list[ArchivedLine]:
    """A meeting's lines in the archive's form, read page by page from its partition."""
    return [
        ArchivedLine(**row)
        async for rows in _pages(transactions, scope, meeting_id, ARCHIVED_COLUMNS)
        for row in rows
    ]


def _exported(meeting_id: UUID, line: ArchivedLine) -> dict[str, Any]:
    """An archived line as the export shows a stored one."""
    return {
        "session_id": meeting_id, "seq": line.seq, "started_at": line.started_at,
        "start_ms": line.start_ms, "duration_ms": line.duration_ms,
        "speaker_idx": line.speaker_idx, "text": line.text, "origin": line.origin,
    }  # fmt: skip


async def transcript_lines(
    transactions: HomeTransactions,
    archive: TranscriptArchive,
    scope: TenancyScope,
    meetings: Sequence[PersonMeeting],
) -> AsyncIterator[bytes]:
    """The meetings' lines as JSON Lines, meeting by meeting in `seq` order."""
    for meeting in meetings:
        if meeting.archive is None:
            async for rows in _pages(transactions, scope, meeting.id, EXPORTED):
                yield json_lines(rows)
            continue
        lines = await archive.lines(scope.home, meeting.archive[0])
        for start in range(0, len(lines), PAGE_ROWS):
            page = lines[start : start + PAGE_ROWS]
            yield json_lines([_exported(meeting.id, line) for line in page])


async def copy_transcripts(
    transactions: HomeTransactions,
    user_id: UUID,
    meeting_ids: Sequence[UUID],
    homes: tuple[Home, Home],
) -> int:
    """Copy the meetings' lines whole to the other home; how many were read."""
    source, target = homes
    table = LINES
    columns = tuple(table.columns.keys())
    copied = 0
    for meeting_id in meeting_ids:
        async for rows in _pages(transactions, TenancyScope(source, user_id), meeting_id, columns):
            async with transactions.begin(TenancyScope(target, user_id)) as session:
                await session.execute(insert(table).values(rows).on_conflict_do_nothing())
            copied += len(rows)
    return copied


async def copy_archives(
    transactions: HomeTransactions,
    archive: TranscriptArchive,
    meetings: tuple[UUID, Sequence[PersonMeeting]],
    homes: tuple[Home, Home],
) -> None:
    """Archive the meetings' lines in the other home and point its copies at them.

    An archived meeting's lines go as they are; a meeting whose month is due but not yet
    archived goes from its partition straight to the other home's archive, since that
    home's partition of the month may be gone. A repeat writes the same objects.
    """
    user_id, archived = meetings
    source, target = homes
    for meeting in archived:
        if meeting.archive is None:
            lines = await stored_lines(transactions, TenancyScope(source, user_id), meeting.id)
            data, count = encode_lines(lines), len(lines)
        else:
            data, count = await archive.raw(source, meeting.archive[0]), meeting.archive[1]
        key = archive_key(meeting.id)
        await archive.put(target, key, data)
        async with transactions.begin(TenancyScope(target, user_id)) as session:
            await session.execute(
                update(MeetingRecord)
                .where(MeetingRecord.id == meeting.id)
                .values(transcript_archive_key=key, transcript_archive_lines=count)
            )
