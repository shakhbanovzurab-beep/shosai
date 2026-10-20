"""What the notes' stages read of a meeting, in their short reading transactions.

The meeting itself, refused as gone once deleted; its lines in the order they were spoken,
read within the meeting's partition; the owner's cross-border consent for the call's
context (nfr-14). The transcript's budget follows the AI port's context cap, less what the
instructions and the findings' list take, at the port's own count of characters a token.
"""

from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.spend.estimates import CHARS_PER_TOKEN
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import CONSENT_READER
from shosai.features.notes.application.pipeline import StageFailedError
from shosai.features.notes.domain.transcript_text import SpokenLine, numbered
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    TranscriptLineRecord,
)

MEETING_GONE: Final = "meeting_gone"
TRANSCRIPT_EMPTY: Final = "transcript_empty"
# Инструкции, заголовки и запас оценки; остальной контекст — расшифровке.
RESERVED_TOKENS: Final = 4_000
BUDGET_FLOOR: Final = 4_000


def transcript_budget(context_tokens: int) -> int:
    """Characters of transcript one call may carry under the port's context cap."""
    return max((context_tokens - RESERVED_TOKENS) * CHARS_PER_TOKEN, BUDGET_FLOOR)


async def present_meeting(session: AsyncSession, meeting_id: UUID) -> MeetingRecord:
    """The meeting; a deleted or missing one fails the stage for good."""
    meeting = await session.get(MeetingRecord, meeting_id)
    if meeting is None or meeting.deleted_at is not None:
        raise StageFailedError(MEETING_GONE)
    return meeting


async def spoken_lines(session: AsyncSession, meeting: MeetingRecord) -> list[SpokenLine]:
    """The meeting's lines, numbered in the order they were spoken."""
    rows = await session.execute(
        select(
            TranscriptLineRecord.start_ms,
            TranscriptLineRecord.duration_ms,
            TranscriptLineRecord.speaker_idx,
            TranscriptLineRecord.text,
        )
        .where(
            TranscriptLineRecord.session_id == meeting.id,
            TranscriptLineRecord.meeting_started_at == meeting.started_at,
        )
        .order_by(TranscriptLineRecord.start_ms, TranscriptLineRecord.seq)
    )
    return numbered([(row.start_ms, row.duration_ms, row.speaker_idx, row.text) for row in rows])


async def cross_border(session: AsyncSession, ports: PortDirectory, user_id: UUID) -> bool:
    """Whether the owner consents to their meeting reaching a provider abroad."""
    return await ports.get(CONSENT_READER).cross_border(session, user_id)
