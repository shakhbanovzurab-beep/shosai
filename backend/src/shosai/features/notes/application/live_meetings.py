"""Binding a live socket to a meeting (`session.start`): capture's `LiveMeetings` port.

The person's active meeting they manage, with its title, whether it is kept and when it
must end (start + 6 hours, MT-D2); any other meeting is `MeetingNotFoundError`, the same
answer for a missing, a foreign, an ended or a deleted one.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.notes.contracts import LiveMeeting, MeetingNotFoundError
from shosai.features.notes.domain.meetings import MeetingStatus, ends_by
from shosai.features.notes.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    MeetingRecord,
)
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer


class LiveMeetingBinder:
    """The `meetings.live_meetings` binding."""

    def __init__(self, ports: PortDirectory) -> None:
        self._ports = ports

    async def bind(self, session: AsyncSession, user_id: UUID, meeting_id: UUID) -> LiveMeeting:
        """The person's active meeting, read in capture's transaction of the person."""
        policy = self._ports.get(ACCESS_POLICY)
        record = await session.scalar(
            select(MeetingRecord).where(
                MeetingRecord.id == meeting_id,
                policy.manageable(MEETING_RESOURCE, Viewer(user_id)),
                MeetingRecord.status == MeetingStatus.ACTIVE.value,
                MeetingRecord.deleted_at.is_(None),
            )
        )
        if record is None:
            raise MeetingNotFoundError
        return LiveMeeting(
            meeting_id=record.id,
            title=record.title,
            kept=record.kept,
            started_at=record.started_at,
            ends_by=ends_by(record.started_at),
        )
