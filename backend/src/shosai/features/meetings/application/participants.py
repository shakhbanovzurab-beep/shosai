"""The participants of a meeting (plan step 7b): added by address, removed when added by hand.

Whoever may manage the meeting adds a participant by address, normalised; adding an address
the meeting already has answers that participant, so a repeat changes nothing (the address
is unique per meeting in the database). A meeting lists at most 100. Only participants a
person added can be removed: those from the calendar or the speakers stay. Changes are
written in the meeting's own scope.
"""

from dataclasses import dataclass
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.library import MeetingReadOnlyError
from shosai.features.meetings.application.visibility import meeting_for, meeting_scope
from shosai.features.meetings.domain.library import (
    LibraryRule,
    LibraryRuleError,
    ParticipantSource,
    may_add_participant,
    normalized_email,
    participant_name,
    removable,
)
from shosai.features.meetings.infrastructure.meeting_records import (
    ParticipantRecord,
)
from shosai.features.workspaces.contracts import ACCESS_POLICY


@dataclass(frozen=True, slots=True)
class Added:
    """A participant after an add, and whether the add created them."""

    participant: ParticipantRecord
    created: bool


class Participants:
    """Adds and removes a meeting's participants."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def add(
        self, principal: Principal, meeting_id: UUID, address: tuple[str, str | None]
    ) -> Added:
        """Add a participant by address; the one already there for a repeat."""
        raw_email, raw_name = address
        try:
            email = normalized_email(raw_email)
        except LibraryRuleError as error:
            raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error
        policy = self._ports.get(ACCESS_POLICY)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            scope = await meeting_scope(session, policy, principal.scope(), meeting_id)
        async with self._transactions.begin(scope) as session:
            meeting, manageable = await meeting_for(
                session, policy, principal.user_id, meeting_id, lock=True
            )
            if not manageable:
                raise MeetingReadOnlyError
            by_address = select(ParticipantRecord).where(
                ParticipantRecord.session_id == meeting.id, ParticipantRecord.email == email
            )
            existing = await session.scalar(by_address)
            if existing is not None:
                return Added(existing, created=False)
            count = await session.scalar(
                select(func.count())
                .select_from(ParticipantRecord)
                .where(ParticipantRecord.session_id == meeting.id)
            )
            if not may_add_participant(int(count or 0)):
                raise AppError(LibraryRule.PARTICIPANTS_LIMIT.value, HTTPStatus.CONFLICT)
            await session.execute(
                insert(ParticipantRecord)
                .values(
                    id=new_id(), session_id=meeting.id, user_id=meeting.user_id,
                    org_id=meeting.org_id, email=email, name=participant_name(raw_name),
                    source=ParticipantSource.ADDED.value,
                )
                .on_conflict_do_nothing(
                    index_elements=[ParticipantRecord.session_id, ParticipantRecord.email],
                    index_where=text("email IS NOT NULL"),
                )
            )  # fmt: skip
            added = await session.scalar(by_address.execution_options(populate_existing=True))
            if added is None:
                message = "участник встречи не добавлен и не найден"
                raise RuntimeError(message)
            return Added(added, created=True)

    async def remove(self, principal: Principal, meeting_id: UUID, participant_id: UUID) -> None:
        """Remove a participant the person added; `participant_not_removable` for the others."""
        policy = self._ports.get(ACCESS_POLICY)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            scope = await meeting_scope(session, policy, principal.scope(), meeting_id)
        async with self._transactions.begin(scope) as session:
            meeting, manageable = await meeting_for(
                session, policy, principal.user_id, meeting_id, lock=True
            )
            if not manageable:
                raise MeetingReadOnlyError
            participant = await session.scalar(
                select(ParticipantRecord).where(
                    ParticipantRecord.id == participant_id,
                    ParticipantRecord.session_id == meeting.id,
                )
            )
            if participant is None:
                raise AppError("participant_not_found", HTTPStatus.NOT_FOUND)
            if not removable(ParticipantSource(participant.source)):
                raise AppError("participant_not_removable", HTTPStatus.CONFLICT)
            await session.delete(participant)
