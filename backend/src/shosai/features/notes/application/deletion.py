"""The owner's deletion of a meeting (MT-D8): hidden at once, gone for good after 7 days.

The cabinet's `DELETE /v1/notes/{id}` and the native `DELETE /v1/me/sessions/{id}` hide
the meeting in one transaction of its scope: `visible_meetings` serves it to nobody, its
share link and comments go (a restore brings it back shared nowhere), and
`notes.meeting.deleted` tells workspaces and the others. Its rows stay for the purge
(`hidden_meetings.py`) and its minutes stay counted. Only the owner deletes, and never a
live meeting.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

import structlog
from sqlalchemy import delete

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.notes.application.visibility import meeting_for, meeting_scope
from shosai.features.notes.contracts.events import MeetingDeleted
from shosai.features.notes.domain.deletion import DeletionRule, deletion_refusal
from shosai.features.notes.domain.meetings import MeetingStatus
from shosai.features.notes.infrastructure.share_records import ShareLinkRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY

STATUSES = {DeletionRule.NOT_OWNER: HTTPStatus.FORBIDDEN, DeletionRule.LIVE: HTTPStatus.CONFLICT}
log = structlog.stdlib.get_logger(__name__)


class MeetingDeletion:
    """Hides the meetings their owners delete."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, EventOutbox],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._outbox = collaborators
        self._clock = clock

    async def delete(self, principal: Principal, meeting_id: UUID) -> None:
        """Hide the meeting; 404 for one the person may not read, 403 or 409 for the rules."""
        policy = self._ports.get(ACCESS_POLICY)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            scope = await meeting_scope(session, policy, principal.scope(), meeting_id)
        async with self._transactions.begin(scope) as session:
            meeting, _ = await meeting_for(
                session, policy, principal.user_id, meeting_id, lock=True
            )
            refusal = deletion_refusal(
                owner=meeting.user_id == principal.user_id,
                live=meeting.status == MeetingStatus.ACTIVE.value,
            )
            if refusal is not None:
                raise AppError(refusal.value, STATUSES[refusal])
            now = self._clock()
            meeting.deleted_at, meeting.updated_at = now, now
            await session.execute(
                delete(ShareLinkRecord).where(ShareLinkRecord.session_id == meeting.id)
            )
            await self._outbox.add(
                session,
                MeetingDeleted(
                    meeting_id=meeting.id, user_id=meeting.user_id, org_id=meeting.org_id
                ),
            )
        log.info("Встреча удалена: скрыта на 7 дней", meeting_id=str(meeting_id))
