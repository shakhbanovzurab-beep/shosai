"""Support's view of a person's deleted meetings and their restore (MT-D8, as files' FL-D5).

Support pages a person's meetings deleted within 7 days in the person's home and restores
one: it comes back in its scope, shared nowhere (its link went with the deletion), with
`meetings.meeting.restored`. While the account is in identity's deletion window support
neither lists nor restores its meetings (409 `account_deletion_scheduled`): only
cancelling the deletion brings them back. Every list and every restore goes to the admin's
EU audit log through identity's port, in the same transaction.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Table, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.account_data.handlers import AccountRef
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import OPERATOR_AUDIT, OperatorAction
from shosai.features.meetings.application.account_window import account_hidden
from shosai.features.meetings.contracts.events import MeetingRestored
from shosai.features.meetings.domain.deletion import purge_after
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord

MEETINGS: Final = cast("Table", MeetingRecord.__table__)
HIDDEN_ORDER: Final = Keyset((MEETINGS.c.deleted_at, MEETINGS.c.id), descending=True)


class HiddenPosition(BaseModel):
    """Where a page of deleted meetings ended."""

    deleted_at: datetime
    meeting_id: UUID


HIDDEN_CURSOR: Final = CursorCodec("meetings.hidden", HiddenPosition)


@dataclass(frozen=True, slots=True)
class HiddenMeeting:
    """A deleted meeting support may still bring back."""

    meeting_id: UUID
    title: str
    started_at: datetime
    seconds: int
    deleted_at: datetime


def in_deletion_window() -> AppError:
    """The account waits for its erasure; only the person's cancelling brings meetings back."""
    return AppError("account_deletion_scheduled", HTTPStatus.CONFLICT)


def hidden_meeting_not_found() -> AppError:
    """No meeting of the person's deleted within the last 7 days by that id."""
    return AppError("hidden_meeting_not_found", HTTPStatus.NOT_FOUND)


class SupportMeetings:
    """Support's page and restore of a person's deleted meetings, each one audited."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, EventOutbox],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._outbox = collaborators
        self._clock = clock

    async def of_person(
        self, home: Home, user_id: UUID, request: PageRequest
    ) -> Page[HiddenMeeting]:
        """The person's deleted meetings, the latest deletion first; the reading is audited."""
        after = None
        if request.cursor is not None:
            position = HIDDEN_CURSOR.decode(request.cursor)
            after = (position.deleted_at, position.meeting_id)
        statement = select(MeetingRecord).where(
            MeetingRecord.user_id == user_id,
            MeetingRecord.deleted_at > purge_after(self._clock()),
        )
        async with self._transactions.begin(TenancyScope(home, user_id)) as session:
            if await account_hidden(session, user_id):
                raise in_deletion_window()
            rows = (await session.scalars(HIDDEN_ORDER.page(statement, after, request.limit))).all()
            await self._audit(session, AccountRef(user_id, home), OperatorAction.MEETINGS_LISTED)
        found = [
            HiddenMeeting(r.id, r.title, r.started_at, r.seconds, r.deleted_at)
            for r in rows
            if r.deleted_at is not None
        ]
        return page_of(
            found, request, HIDDEN_CURSOR, lambda m: m,
            lambda m: HiddenPosition(deleted_at=m.deleted_at, meeting_id=m.meeting_id),
        )  # fmt: skip

    async def restore(self, home: Home, user_id: UUID, meeting_id: UUID) -> None:
        """Bring a deleted meeting back, shared nowhere; audited."""
        async with self._transactions.begin(TenancyScope(home, user_id), read_only=True) as session:
            org_id = await session.scalar(
                select(MeetingRecord.org_id).where(
                    MeetingRecord.id == meeting_id, MeetingRecord.user_id == user_id
                )
            )
        async with self._transactions.begin(TenancyScope(home, user_id, org_id)) as session:
            if await account_hidden(session, user_id):
                raise in_deletion_window()
            meeting = await session.scalar(
                select(MeetingRecord)
                .where(
                    MeetingRecord.id == meeting_id,
                    MeetingRecord.user_id == user_id,
                    MeetingRecord.deleted_at > purge_after(self._clock()),
                )
                .with_for_update()
            )
            if meeting is None:
                raise hidden_meeting_not_found()
            meeting.deleted_at, meeting.updated_at = None, self._clock()
            await self._outbox.add(
                session,
                MeetingRestored(meeting_id=meeting.id, user_id=user_id, org_id=meeting.org_id),
            )
            target = AccountRef(user_id, home)
            await self._audit(session, target, OperatorAction.MEETING_RESTORED, meeting.id)

    async def _audit(
        self,
        session: AsyncSession,
        target: AccountRef,
        action: OperatorAction,
        subject_id: UUID | None = None,
    ) -> None:
        await self._ports.get(OPERATOR_AUDIT).acted(session, target, action, subject_id)
