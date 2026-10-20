"""How many meetings the library holds: every one the person may read, and theirs per folder.

The cabinet's folder pills show these counts while the library itself pages by cursor, so
they come from the server in two statements over the person's meetings: one count through
`visible_meetings` (the access policy, nothing deleted or hidden), one grouped count of
their own personal meetings by folder, as only the owner files a meeting.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.notes.application.visibility import visible_meetings
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer


@dataclass(frozen=True, slots=True)
class LibraryCounts:
    """Every meeting the person may read, and their own meetings in each of their folders."""

    every: int
    by_folder: Mapping[UUID, int]


class MeetingCounts:
    """Counts the library's meetings for its pills."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def of(self, principal: Principal) -> LibraryCounts:
        """The counts as they are now."""
        visible = visible_meetings(self._ports.get(ACCESS_POLICY), Viewer(principal.user_id))
        filed = (
            visible.with_only_columns(MeetingRecord.folder_id, func.count())
            .where(
                MeetingRecord.user_id == principal.user_id,
                MeetingRecord.org_id.is_(None),
                MeetingRecord.folder_id.is_not(None),
            )
            .group_by(MeetingRecord.folder_id)
        )
        every = select(func.count()).select_from(
            visible.with_only_columns(MeetingRecord.id).subquery()
        )
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            total = await session.scalar(every)
            rows = await session.execute(filed)
            by_folder = {folder_id: int(count) for folder_id, count in rows if folder_id}
        return LibraryCounts(every=int(total or 0), by_folder=by_folder)
