"""A meeting's one share link, as whoever may manage the meeting keeps it (step 13, MT-D5).

`PUT` turns the link on with its settings or changes them: the first gives a new token,
a change keeps it, and the expiry is counted anew only when a different one is chosen.
`DELETE` turns it off — the row goes with its comments, so turning it on again gives a
new token. A meeting not kept has no link (409 `private_meeting`, MT-D6); a reader who
may not manage the meeting gets 403 `meeting_read_only`. Changes are written in the
meeting's own scope.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

import structlog
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.library import MeetingReadOnlyError
from shosai.features.meetings.application.visibility import meeting_for, meeting_scope
from shosai.features.meetings.domain.meetings import PRIVATE_MEETING
from shosai.features.meetings.domain.sharing import (
    ShareExpiry,
    ShareSettings,
    new_token,
    next_expires_at,
)
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.share_records import ShareLinkRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY

log = structlog.stdlib.get_logger(__name__)


def settings_of(link: ShareLinkRecord) -> ShareSettings:
    """The link's settings as stored."""
    return ShareSettings(
        show_transcript=link.show_transcript, show_names=link.show_names,
        allow_comments=link.allow_comments, expiry=ShareExpiry(link.expiry),
    )  # fmt: skip


class ShareLinks:
    """Keeps meetings' share links."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._clock = clock

    async def link(self, principal: Principal, meeting_id: UUID) -> ShareLinkRecord | None:
        """The meeting's link, None while it is off."""
        scope = await self._scope(principal, meeting_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            await self._managed(session, principal, meeting_id, lock=False)
            return await session.get(ShareLinkRecord, meeting_id)

    async def put(
        self, principal: Principal, meeting_id: UUID, settings: ShareSettings
    ) -> ShareLinkRecord:
        """Turn the link on with the settings, or change them; the token is kept."""
        scope = await self._scope(principal, meeting_id)
        now = self._clock()
        async with self._transactions.begin(scope) as session:
            meeting = await self._managed(session, principal, meeting_id, lock=True)
            if not meeting.kept:
                raise AppError(PRIVATE_MEETING, HTTPStatus.CONFLICT)
            link = await session.get(ShareLinkRecord, meeting.id)
            if link is None:
                link = ShareLinkRecord(
                    session_id=meeting.id, user_id=meeting.user_id, org_id=meeting.org_id,
                    token=new_token(), created_at=now,
                    expires_at=next_expires_at(None, settings, None, now),
                )  # fmt: skip
                session.add(link)
                log.info("Ссылка на встречу включена", meeting_id=str(meeting.id))
            else:
                link.expires_at = next_expires_at(settings_of(link), settings, link.expires_at, now)
            link.show_transcript, link.show_names = settings.show_transcript, settings.show_names
            link.allow_comments, link.expiry = settings.allow_comments, settings.expiry.value
            link.updated_at = now
            return link

    async def remove(self, principal: Principal, meeting_id: UUID) -> None:
        """Turn the link off; its comments go with it. Off already, nothing changes."""
        scope = await self._scope(principal, meeting_id)
        async with self._transactions.begin(scope) as session:
            meeting = await self._managed(session, principal, meeting_id, lock=True)
            removed = await session.execute(
                delete(ShareLinkRecord)
                .where(ShareLinkRecord.session_id == meeting.id)
                .returning(ShareLinkRecord.session_id)
            )
            if removed.first() is not None:
                log.info("Ссылка на встречу выключена", meeting_id=str(meeting.id))

    async def _scope(self, principal: Principal, meeting_id: UUID) -> TenancyScope:
        policy = self._ports.get(ACCESS_POLICY)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return await meeting_scope(session, policy, principal.scope(), meeting_id)

    async def _managed(
        self, session: AsyncSession, principal: Principal, meeting_id: UUID, *, lock: bool
    ) -> MeetingRecord:
        policy = self._ports.get(ACCESS_POLICY)
        meeting, manageable = await meeting_for(
            session, policy, principal.user_id, meeting_id, lock=lock
        )
        if not manageable:
            raise MeetingReadOnlyError
        return meeting
