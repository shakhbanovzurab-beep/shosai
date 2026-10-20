"""What a meeting's stored transcript says of it: how many lines and when the last one ends."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.notes.domain.transcript import LineOrigin
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)


async def spoken(session: AsyncSession, record: MeetingRecord) -> tuple[int, datetime | None]:
    """How many lines the meeting has and when its last one ends, from its own partition."""
    row = (
        await session.execute(
            select(
                func.count(),
                func.max(TranscriptLineRecord.start_ms + TranscriptLineRecord.duration_ms),
            ).where(
                TranscriptLineRecord.session_id == record.id,
                TranscriptLineRecord.meeting_started_at == record.started_at,
            )
        )
    ).one()
    last_end_ms: int | None = row[1]
    if last_end_ms is None:
        return int(row[0]), None
    return int(row[0]), record.started_at + timedelta(milliseconds=last_end_ms)


async def live_seqs_up_to(session: AsyncSession, record: MeetingRecord, highest: int) -> int:
    """How many live lines of the meeting have a `seq` from 1 to `highest`."""
    count = await session.scalar(
        select(func.count()).where(
            TranscriptLineRecord.session_id == record.id,
            TranscriptLineRecord.meeting_started_at == record.started_at,
            TranscriptLineRecord.origin == LineOrigin.LIVE.value,
            TranscriptLineRecord.seq <= highest,
        )
    )
    return int(count or 0)
