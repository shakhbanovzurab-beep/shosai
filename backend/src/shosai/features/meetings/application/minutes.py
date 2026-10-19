"""The seconds of a person's meetings that still exist, for billing's month (BL-D3, MT-D3).

Billing counts the month's minutes live, never cached: the meetings meetings still holds,
by their start, plus the tombstones of deleted ones. An ended meeting counts its seconds;
a live one counts from its start until now, within the 6-hour ceiling; a meeting hidden
by a deletion still counts until the purge leaves its tombstone.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Float, case, cast, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.meetings.domain.meetings import MeetingStatus
from shosai.features.meetings.domain.minutes import MAX_SECONDS
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord


class MeetingMinutesCount:
    """The `billing.meeting_minutes` binding."""

    def __init__(self, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._clock = clock

    async def recorded_seconds(
        self, session: AsyncSession, user_id: UUID, window: tuple[datetime, datetime]
    ) -> int:
        """Seconds of the person's meetings started in `[start, end)`, in their transaction."""
        start, end = window
        elapsed = func.extract("epoch", literal(self._clock()) - MeetingRecord.started_at)
        live = func.least(func.greatest(cast(elapsed, Float), 0), MAX_SECONDS)
        seconds = case(
            (MeetingRecord.status == MeetingStatus.ACTIVE.value, func.floor(live)),
            else_=MeetingRecord.seconds,
        )
        total = await session.scalar(
            select(func.coalesce(func.sum(seconds), 0)).where(
                MeetingRecord.user_id == user_id,
                MeetingRecord.started_at >= start,
                MeetingRecord.started_at < end,
            )
        )
        return int(total or 0)
