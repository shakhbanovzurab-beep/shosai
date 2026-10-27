"""The admin's hand on a call: ending a room for everyone and removing a participant (MR-D10).

The admin names a room by its LiveKit name, found in whichever home holds it. Each action is
written to the admin's EU audit log through identity's port in the same transaction as its
own row (inv-17), against the room's owner, naming the room: a close marks the room closed by
`admin` and only then ends it in the SFU; a removal bans the session's principal — by `admin`
— before it revokes their passes and disconnects them, as the owner's removal does. The owner
is not removed from their own room: the admin ends the room instead. When the SFU does not
answer, the row and the audit stay and the action answers 503; repeating it is safe, and the
sweep ends a closed room the SFU still holds.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from http import HTTPStatus

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.account_data.handlers import AccountRef
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import OPERATOR_AUDIT, OperatorAction
from shosai.features.meetings.application.joining import FoundRoom
from shosai.features.meetings.application.removals import (
    ParticipantNotFoundError,
    ban,
    disconnect,
)
from shosai.features.meetings.application.video_server import VideoServer
from shosai.features.meetings.contracts import RoomNotFoundError
from shosai.features.meetings.domain.principals import Principal, principal_of
from shosai.features.meetings.domain.rooms import ClosedBy, RoomState
from shosai.features.meetings.infrastructure.room_passes import RoomPasses
from shosai.features.meetings.infrastructure.room_records import BANNED_BY_ADMIN, RoomRecord

log = structlog.stdlib.get_logger(__name__)


class AdminRoomActions:
    """Ends rooms and removes participants for the admin, each one audited."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[VideoServer, RoomPasses, PortDirectory],
        find: Callable[[str], Awaitable[FoundRoom | None]],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._server, self._passes, self._ports = collaborators
        self._find = find
        self._clock = clock

    async def end(self, name: str) -> None:
        """Close the room for good and end it in the SFU for everyone."""
        found = await self._room(name)
        async with self._transactions.begin(self._scope(found)) as session:
            record = await self._locked(session, found)
            if record.state == RoomState.OPEN.value:
                now = self._clock()
                record.state, record.closed_at = RoomState.CLOSED.value, now
                record.closed_by, record.updated_at = ClosedBy.ADMIN.value, now
            await self._ports.get(OPERATOR_AUDIT).acted(
                session, AccountRef(found.owner_id, found.home), OperatorAction.ROOM_CLOSED,
                found.room_id,
            )  # fmt: skip
        await self._server.delete_room(name)
        log.info("Администратор закончил комнату", room_id=str(found.room_id))

    async def remove(self, name: str, identity: str) -> None:
        """Ban the session's principal from the room and disconnect every session of theirs."""
        target = principal_of(identity)
        if target is None:
            raise ParticipantNotFoundError
        found = await self._room(name)
        if target == Principal.of_user(found.owner_id):
            raise AppError("cannot_remove_owner", HTTPStatus.CONFLICT)
        async with self._transactions.begin(self._scope(found)) as session:
            record = await self._locked(session, found)
            await session.execute(ban(record, target, BANNED_BY_ADMIN))
            await self._ports.get(OPERATOR_AUDIT).acted(
                session, AccountRef(found.owner_id, found.home),
                OperatorAction.ROOM_PARTICIPANT_REMOVED, found.room_id,
            )  # fmt: skip
        revoked = await disconnect((self._server, self._passes), record, target)
        log.info("Администратор удалил участника", room_id=str(found.room_id), passes=revoked)

    async def _room(self, name: str) -> FoundRoom:
        found = await self._find(name)
        if found is None:
            raise RoomNotFoundError
        return found

    @staticmethod
    async def _locked(session: AsyncSession, found: FoundRoom) -> RoomRecord:
        record = await session.scalar(
            select(RoomRecord).where(RoomRecord.id == found.room_id).with_for_update()
        )
        if record is None:
            raise RoomNotFoundError
        return record

    @staticmethod
    def _scope(found: FoundRoom) -> TenancyScope:
        return TenancyScope(found.home, found.owner_id, found.org_id)
