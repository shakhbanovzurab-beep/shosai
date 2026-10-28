"""Rows of meetings' tables for the tests: a room with a call, a ban, a message, a recording
and a board, written as their owner."""

import uuid
from datetime import UTC, datetime
from uuid import UUID

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.domain.invites import new_invite_token
from shosai.features.meetings.domain.rooms import new_livekit_name
from shosai.features.meetings.infrastructure.call_records import (
    RoomChatMessageRecord,
    RoomRecordingRecord,
    RoomWhiteboardRecord,
)
from shosai.features.meetings.infrastructure.room_records import (
    RoomBanRecord,
    RoomCallRecord,
    RoomRecord,
)
from shosai.features.meetings.infrastructure.stream_records import (
    StreamBanRecord,
    StreamChatMessageRecord,
    StreamMemberRecord,
    StreamRecord,
)
from tests.harness.database_access import DatabaseAccess

GUEST = "guest-0123456789ab"
STARTED = datetime(2026, 10, 27, 10, tzinfo=UTC)


def room_row(owner: UUID, org: UUID | None = None, /, **fields: object) -> RoomRecord:
    """An open room of the owner, in Personal unless a space is given."""
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "owner_id": owner,
        "org_id": org,
        "lk_room_name": new_livekit_name(),
        "invite_token": new_invite_token(),
    }
    return RoomRecord(**(values | fields))


async def add_room(
    homes: DatabaseAccess, room: RoomRecord, *, home: Home = Home.RU, with_kept: bool = True
) -> RoomRecord:
    """Write the room as its owner in its space; with a live call, a ban, a message, an active
    recording and a board unless asked otherwise."""
    owned = {"room_id": room.id, "owner_id": room.owner_id, "org_id": room.org_id}
    call = RoomCallRecord(
        id=uuid.uuid4(), lk_room_sid=f"RM_{uuid.uuid4().hex[:12]}", started_at=STARTED,
        ceiling=4, **owned,
    )  # fmt: skip
    async with homes.transactions.begin(TenancyScope(home, room.owner_id, room.org_id)) as session:
        session.add(room)
        await session.flush()
        if not with_kept:
            return room
        session.add_all(
            [
                call,
                RoomBanRecord(
                    id=uuid.uuid4(), principal=GUEST, banned_by=str(room.owner_id), **owned
                ),
                RoomRecordingRecord(id=uuid.uuid4(), **owned),
                RoomWhiteboardRecord(updated_by=GUEST, **owned),
            ]
        )
        await session.flush()
        session.add(
            RoomChatMessageRecord(
                id=uuid.uuid4(), call_id=call.id, owner_id=room.owner_id, org_id=room.org_id,
                seq=1, principal=GUEST, identity=f"{GUEST}__0a1b2c3d", author="Гость",
                body="Привет",
            )
        )  # fmt: skip
    return room


async def add_broadcast(
    homes: DatabaseAccess, room: RoomRecord, *, home: Home = Home.RU
) -> StreamRecord:
    """Make the room a broadcast's, with the owner as its host, a ban and a message."""
    owned = {"owner_id": room.owner_id, "org_id": room.org_id}
    stream = StreamRecord(id=uuid.uuid4(), room_id=room.id, title="Эфир", **owned)
    async with homes.transactions.begin(TenancyScope(home, room.owner_id, room.org_id)) as session:
        session.add(stream)
        await session.flush()
        session.add_all(
            [
                StreamMemberRecord(
                    id=uuid.uuid4(), stream_id=stream.id, principal=str(room.owner_id),
                    display_name="Ведущий", role="host", **owned,
                ),
                StreamBanRecord(
                    id=uuid.uuid4(), stream_id=stream.id, principal=GUEST,
                    banned_by=str(room.owner_id), **owned,
                ),
                StreamChatMessageRecord(
                    id=uuid.uuid4(), stream_id=stream.id, seq=1, principal=GUEST, author="Гость",
                    body="Здравствуйте", **owned,
                ),
            ]
        )  # fmt: skip
    return stream
