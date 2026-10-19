"""Deleted meetings after their 7 hidden days: the purge (MT-D8).

The sweep role only lists what is due; each meeting then goes in its own scope's
transaction, with the deletion of everything under it, billing's tombstone of its minutes
in its month (written once whatever the repeats) and its runs' transient objects named
for deletion; the objects are deleted after that commit. A pass takes at most a batch.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import USAGE_TOMBSTONES
from shosai.features.meetings.domain.deletion import purge_after
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.run_objects import (
    RunObjects,
    record_deletions,
    run_keys,
)
from shosai.features.meetings.infrastructure.run_records import RunRecord

BATCH: Final = 200
log = structlog.stdlib.get_logger(__name__)


class HiddenMeetings:
    """The purge of meetings deleted more than 7 days ago."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, RunObjects],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._objects = collaborators
        self._clock = clock

    async def purge(self, home: Home) -> int:
        """Remove meetings hidden for more than 7 days; how many went."""
        cutoff = purge_after(self._clock())
        due = (
            select(MeetingRecord.id, MeetingRecord.user_id, MeetingRecord.org_id)
            .where(MeetingRecord.deleted_at <= cutoff)
            .order_by(MeetingRecord.deleted_at)
            .limit(BATCH)
        )
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rows = (await session.execute(due)).all()
        gone = 0
        for meeting_id, user_id, org_id in rows:
            gone += await self._purge_one(TenancyScope(home, user_id, org_id), meeting_id, cutoff)
        if gone:
            log.info("Удалённые встречи стёрты окончательно", home=home.value, meetings=gone)
        return gone

    async def _purge_one(self, scope: TenancyScope, meeting_id: UUID, cutoff: datetime) -> int:
        async with self._transactions.begin(scope) as session:
            meeting = await session.scalar(
                select(MeetingRecord)
                .where(MeetingRecord.id == meeting_id, MeetingRecord.deleted_at <= cutoff)
                .with_for_update()
            )
            if meeting is None:
                return 0
            keys = await run_keys(session, RunRecord.session_id == meeting.id)
            await record_deletions(session, keys)
            await self._ports.get(USAGE_TOMBSTONES).meeting_deleted(
                session, meeting.user_id, (meeting.id, meeting.started_at), meeting.seconds
            )
            await session.delete(meeting)
        await self._objects.delete(scope.home, keys)
        return 1
