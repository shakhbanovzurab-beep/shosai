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
from shosai.features.notes.application.library import MeetingReadOnlyError
from shosai.features.notes.application.visibility import meeting_for, meeting_scope
from shosai.features.notes.domain.meetings import PRIVATE_MEETING
from shosai.features.notes.domain.sharing import (
    ShareExpiry,
    ShareSettings,
    new_token,
    next_expires_at,
)
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.share_records import ShareLinkRecord
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
        scope = await self.scope_of(principal, meeting_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            await self._managed(session, principal, meeting_id, lock=False)
            return await session.get(ShareLinkRecord, meeting_id)

    async def put(
        self, principal: Principal, meeting_id: UUID, settings: ShareSettings
    ) -> ShareLinkRecord:
        """Turn the link on with the settings, or change them; the token is kept."""
        scope = await self.scope_of(principal, meeting_id)
        async with self._transactions.begin(scope) as session:
            return await self.put_in(session, principal, meeting_id, settings)

    async def put_in(
        self,
        session: AsyncSession,
        principal: Principal,
        meeting_id: UUID,
        settings: ShareSettings,
    ) -> ShareLinkRecord:
        """`put` in the caller's transaction of the meeting's scope (Leo's write tool)."""
        now = self._clock()
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
        await session.flush()
        return link

    async def remove(self, principal: Principal, meeting_id: UUID) -> None:
        """Turn the link off; its comments go with it. Off already, nothing changes."""
        scope = await self.scope_of(principal, meeting_id)
        async with self._transactions.begin(scope) as session:
            await self.remove_in(session, principal, meeting_id)

    async def remove_in(
        self, session: AsyncSession, principal: Principal, meeting_id: UUID
    ) -> bool:
        """`remove` in the caller's transaction of the meeting's scope; whether a link went."""
        meeting = await self._managed(session, principal, meeting_id, lock=True)
        removed = await session.execute(
            delete(ShareLinkRecord)
            .where(ShareLinkRecord.session_id == meeting.id)
            .returning(ShareLinkRecord.session_id)
        )
        if removed.first() is None:
            return False
        log.info("Ссылка на встречу выключена", meeting_id=str(meeting.id))
        return True

    async def scope_of(self, principal: Principal, meeting_id: UUID) -> TenancyScope:
        """The scope the meeting's link is changed in; `MeetingNotFoundError` if unreadable."""
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
