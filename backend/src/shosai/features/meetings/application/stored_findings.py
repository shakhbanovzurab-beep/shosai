"""The findings a run wrote for a meeting, read back in their order with their ids."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.meetings.domain.findings import Evidence, Finding, FindingKind
from shosai.features.meetings.infrastructure.notes_records import FindingRecord


def finding_of(record: FindingRecord) -> Finding:
    """A stored finding as the domain keeps it."""
    return Finding(
        kind=FindingKind(record.kind),
        text=record.text,
        evidence=Evidence(record.start_ms, record.end_ms, record.quote),
        topic=record.topic,
        owner_speaker=record.owner_speaker,
        owner_name=record.owner_name,
        due_on=record.due_on,
    )


async def findings_of(
    session: AsyncSession, meeting_id: UUID, run_id: UUID | None
) -> list[tuple[UUID, Finding]]:
    """The run's findings of the meeting by position; none for no run."""
    if run_id is None:
        return []
    records = await session.scalars(
        select(FindingRecord)
        .where(FindingRecord.session_id == meeting_id, FindingRecord.run_id == run_id)
        .order_by(FindingRecord.position)
    )
    return [(record.id, finding_of(record)) for record in records]
