"""A share link's token resolved to its link, for anyone holding it (step 13, MT-D5, §7).

The token is looked up in both homes at once: `meetings_shared_meeting(token)` answers,
past row-level security, the meeting and company of the link, and a link migrated or
transferred answers from its home. The meeting's owner is then read in its company's scope,
and the page in the owner's, with the link and its state checked in the page's own
transaction (`checked`). A token that is not well
formed, unknown, expired, of a hidden or not-kept meeting or of an account in its deletion
window gets the one answer, 404 `share_not_found`; a home that does not answer is 503, not
that answer.
"""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.application.account_window import account_hidden
from shosai.features.meetings.domain.sharing import LinkState, resolves, well_formed
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.share_records import ShareLinkRecord

LOOKUP: Final = text("SELECT session_id, org_id FROM meetings_shared_meeting(:token)")


class ShareNotFoundError(AppError):
    """No link opens with this token, whatever the reason (404)."""

    def __init__(self) -> None:
        super().__init__("share_not_found", HTTPStatus.NOT_FOUND)


class SharedLinks:
    """Resolves a token to the link it opens, in whichever home holds it."""

    def __init__(
        self,
        transactions: HomeTransactions,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._clock = clock

    async def resolve(self, token: str) -> tuple[Home, UUID, UUID | None]:
        """The home, meeting and company of the token's link; `share_not_found` without one."""
        if not well_formed(token):
            raise ShareNotFoundError
        answers = await asyncio.gather(
            *(self._lookup(home, token) for home in Home), return_exceptions=True
        )
        found: list[tuple[Home, UUID, UUID | None]] = []
        silent: HomeUnavailableError | None = None
        for home, answer in zip(Home, answers, strict=True):
            if isinstance(answer, HomeUnavailableError):
                silent = answer
            elif isinstance(answer, BaseException):
                raise answer
            elif answer is not None:
                found.append((home, *answer))
        if found:
            return found[0]
        if silent is not None:
            # Молчит дом, где ссылка могла быть: это 503, а не «ссылки нет».
            raise silent
        raise ShareNotFoundError

    async def _lookup(self, home: Home, token: str) -> tuple[UUID, UUID | None] | None:
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            row = (await session.execute(LOOKUP, {"token": token})).first()
        return None if row is None else (row[0], row[1])

    async def located(self, token: str) -> tuple[TenancyScope, UUID]:
        """The owner's scope the token's page is read in, and its meeting."""
        home, meeting_id, org_id = await self.resolve(token)
        company = TenancyScope(home, None, org_id)
        async with self._transactions.begin(company, read_only=True) as session:
            owner = await session.scalar(
                select(MeetingRecord.user_id).where(MeetingRecord.id == meeting_id)
            )
        if owner is None:
            raise ShareNotFoundError
        return TenancyScope(home, owner, org_id), meeting_id

    async def checked(
        self, session: AsyncSession, token: str, meeting_id: UUID
    ) -> tuple[ShareLinkRecord, MeetingRecord]:
        """The link and its meeting in the owner's scope, if the link still resolves."""
        found = (
            await session.execute(
                select(ShareLinkRecord, MeetingRecord)
                .join(MeetingRecord, MeetingRecord.id == ShareLinkRecord.session_id)
                .where(ShareLinkRecord.token == token, ShareLinkRecord.session_id == meeting_id)
            )
        ).first()
        if found is None:
            raise ShareNotFoundError
        link, meeting = found
        state = LinkState(
            expires_at=link.expires_at, meeting_hidden=meeting.deleted_at is not None,
            meeting_kept=meeting.kept, owner_hidden=await account_hidden(session, meeting.user_id),
        )  # fmt: skip
        if not resolves(state, self._clock()):
            raise ShareNotFoundError
        return link, meeting
