"""The owner's hand on the call: removing someone for good and lowering a hand (MR-D2, MR-D12).

A removal names one session; it bans that session's principal from the room — a person on
every device, a guest by their guest principal — revokes their room passes and disconnects
every session of theirs. The ban is written first, so a principal the SFU could not
disconnect yet is refused on every route and at the door; the SFU part answers 503 and is
repeated safely. The owner cannot remove themselves. Lowering a hand clears that session's
`hand` attribute.
"""

from http import HTTPStatus
from uuid import UUID

import structlog
from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts import Principal as Person
from shosai.features.meetings.application.room_reads import owned_room, room_of
from shosai.features.meetings.application.video_server import VideoServer
from shosai.features.meetings.domain.joining import may_remove
from shosai.features.meetings.domain.principals import Principal, principal_of
from shosai.features.meetings.domain.wire import HAND
from shosai.features.meetings.infrastructure.room_passes import RoomPasses
from shosai.features.meetings.infrastructure.room_records import RoomBanRecord, RoomRecord

log = structlog.stdlib.get_logger(__name__)


class ParticipantNotFoundError(AppError):
    """No such session in the owner's room (404)."""

    def __init__(self) -> None:
        super().__init__("participant_not_found", HTTPStatus.NOT_FOUND)


class Removals:
    """Removals and hands in the owner's rooms."""

    def __init__(
        self, transactions: HomeTransactions, server: VideoServer, passes: RoomPasses
    ) -> None:
        self._transactions = transactions
        self._server = server
        self._passes = passes

    async def remove(self, person: Person, room_id: UUID, identity: str) -> None:
        """Ban the session's principal from the room and disconnect every session of theirs."""
        target = principal_of(identity)
        if target is None:
            raise ParticipantNotFoundError
        record = await self._room(person, room_id)
        owner = Principal.of_user(person.user_id)
        if not may_remove(room_of(record), owner, target):
            raise AppError("cannot_remove_owner", HTTPStatus.CONFLICT)
        scope = TenancyScope(person.home, person.user_id, record.org_id)
        async with self._transactions.begin(scope) as session:
            await session.execute(
                insert(RoomBanRecord)
                .values(
                    id=new_id(),
                    room_id=room_id,
                    owner_id=person.user_id,
                    org_id=record.org_id,
                    principal=target.value,
                    banned_by=owner.value,
                )
                .on_conflict_do_nothing(index_elements=["room_id", "principal"])
            )
        revoked = await self._passes.revoke(room_id, target.value)
        sessions = await self._server.participants(record.lk_room_name)
        for item in sessions:
            if principal_of(item.identity) == target:
                await self._server.remove_participant(record.lk_room_name, item.identity)
        log.info("Участник удалён из комнаты", room_id=str(room_id), passes=revoked)

    async def lower_hand(self, person: Person, room_id: UUID, identity: str) -> None:
        """Clear a session's raised hand."""
        record = await self._room(person, room_id)
        if not await self._server.set_attributes(record.lk_room_name, identity, {HAND: ""}):
            raise ParticipantNotFoundError

    async def _room(self, person: Person, room_id: UUID) -> RoomRecord:
        async with self._transactions.begin(person.scope(), read_only=True) as session:
            return await owned_room(session, person.user_id, room_id)
