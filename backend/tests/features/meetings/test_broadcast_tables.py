"""Broadcasts' tables: a broadcast is its owner's within the owner's spaces, the database keeps
its rules and a deleted room takes its broadcast with everything (meetings A12b, §3.4)."""

import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.infrastructure.room_records import RoomRecord
from shosai.features.meetings.infrastructure.stream_records import (
    StreamBanRecord,
    StreamChatMessageRecord,
    StreamMemberRecord,
    StreamRecord,
)
from tests.features.meetings.room_kit import GUEST, add_broadcast, add_room, room_row
from tests.harness.database_access import DatabaseAccess

MODELS = (StreamRecord, StreamMemberRecord, StreamBanRecord, StreamChatMessageRecord)


async def counts(homes: DatabaseAccess, scope: TenancyScope) -> list[int]:
    """How many rows of each table the scope sees."""
    async with homes.transactions.begin(scope, read_only=True) as session:
        return [
            (await session.scalar(select(func.count()).select_from(model))) or 0 for model in MODELS
        ]


async def test_a_broadcast_and_what_it_keeps_are_its_owners_only(homes: DatabaseAccess) -> None:
    owner, other, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    for space in (None, org):
        await add_broadcast(homes, await add_room(homes, room_row(owner, space), with_kept=False))

    assert await counts(homes, TenancyScope(Home.RU, owner, org)) == [2, 2, 2, 2]
    assert await counts(homes, TenancyScope(Home.RU, owner)) == [1, 1, 1, 1]
    assert await counts(homes, TenancyScope(Home.RU, other, org)) == [0, 0, 0, 0]


@pytest.mark.parametrize(
    "change",
    [
        {"status": "paused"},
        {"status": "ended"},
        {"title": ""},
        {"speaker_limit": 21},
        {"chat_mode": "loud"},
        {"pinned_principal": "anyone"},
    ],
)
async def test_the_database_keeps_a_broadcasts_rules(
    homes: DatabaseAccess, change: dict[str, object]
) -> None:
    owner = uuid.uuid4()
    room = await add_room(homes, room_row(owner), with_kept=False)
    row = {"id": uuid.uuid4(), "room_id": room.id, "owner_id": owner, "title": "Эфир"} | change

    with pytest.raises(IntegrityError):
        async with homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
            session.add(StreamRecord(**row))


async def test_one_broadcast_per_room_one_place_per_principal_and_one_seq_per_broadcast(
    homes: DatabaseAccess,
) -> None:
    owner = uuid.uuid4()
    room = await add_room(homes, room_row(owner), with_kept=False)
    stream = await add_broadcast(homes, room)
    owned = {"owner_id": owner, "org_id": None}
    repeats = [
        StreamRecord(id=uuid.uuid4(), room_id=room.id, title="Второй", **owned),
        StreamMemberRecord(
            id=uuid.uuid4(), stream_id=stream.id, principal=str(owner), display_name="Ещё раз",
            role="speaker", **owned,
        ),
        StreamChatMessageRecord(
            id=uuid.uuid4(), stream_id=stream.id, seq=1, principal=GUEST, author="Гость",
            body="Снова первый", **owned,
        ),
    ]  # fmt: skip

    for repeat in repeats:
        with pytest.raises(IntegrityError):
            async with homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
                session.add(repeat)


async def test_a_deleted_room_takes_its_broadcast_and_everything_it_keeps(
    homes: DatabaseAccess,
) -> None:
    owner = uuid.uuid4()
    room = await add_room(homes, room_row(owner), with_kept=False)
    await add_broadcast(homes, room)

    async with homes.transactions.begin(TenancyScope(Home.RU, owner)) as session:
        await session.execute(delete(RoomRecord).where(RoomRecord.id == room.id))

    assert await counts(homes, TenancyScope(Home.RU, owner)) == [0, 0, 0, 0]
