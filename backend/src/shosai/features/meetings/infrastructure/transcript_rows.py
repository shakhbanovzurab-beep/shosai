"""A person's transcript lines, meeting by meeting: for export, copy and digest (§14 rule 1).

The transcript has no person column — five million lines a day would pay an index for it —
so a person's lines are reached through their meetings, each meeting's lines paged by
`seq` in their own short transactions: no transaction stays open while an archive goes to
storage or across both homes, and no meeting sits whole in memory.
"""

from collections.abc import AsyncIterator, Sequence
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.person_rows import PAGE_ROWS, json_lines
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)

LINES: Final = cast("Table", TranscriptLineRecord.__table__)
# Выгружаются без служебного ключа партиции: он — копия начала встречи.
EXPORTED: Final = (
    "session_id", "seq", "started_at", "start_ms", "duration_ms", "speaker_idx", "text", "origin",
)  # fmt: skip


async def person_meetings(
    transactions: HomeTransactions, scope: TenancyScope, user_id: UUID
) -> list[UUID]:
    """The ids of the person's own meetings in the scope's home, not a workspace's."""
    found: list[UUID] = []
    last: UUID | None = None
    while True:
        query = select(MeetingRecord.id).where(
            MeetingRecord.user_id == user_id, MeetingRecord.org_id.is_(None)
        )
        if last is not None:
            query = query.where(MeetingRecord.id > last)
        async with transactions.begin(scope, read_only=True) as session:
            page = list(
                (await session.scalars(query.order_by(MeetingRecord.id).limit(PAGE_ROWS))).all()
            )
        found.extend(page)
        if len(page) < PAGE_ROWS:
            return found
        last = page[-1]


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


async def transcript_lines(
    transactions: HomeTransactions, scope: TenancyScope, meeting_ids: Sequence[UUID]
) -> AsyncIterator[bytes]:
    """The meetings' lines as JSON Lines, meeting by meeting in `seq` order."""
    for meeting_id in meeting_ids:
        async for rows in _pages(transactions, scope, meeting_id, EXPORTED):
            yield json_lines(rows)


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
