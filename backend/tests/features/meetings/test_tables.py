"""Meetings' tables: a room is its owner's within the owner's spaces, the database keeps the
rules, the lookups answer one room, and the sweep reads what it must (meetings plan §3.4)."""

import uuid

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
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
from tests.features.meetings.room_kit import add_room, room_row
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot

MODELS = (
    RoomRecord,
    RoomCallRecord,
    RoomBanRecord,
    RoomChatMessageRecord,
    RoomRecordingRecord,
    RoomWhiteboardRecord,
)


async def counts(homes: DatabaseAccess, scope: TenancyScope) -> list[int]:
    """How many rows of each table the scope sees."""
    async with homes.transactions.begin(scope, read_only=True) as session:
        return [
            (await session.scalar(select(func.count()).select_from(model))) or 0 for model in MODELS
        ]


async def test_a_room_and_what_it_keeps_are_its_owners_only(homes: DatabaseAccess) -> None:
    owner, other, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await add_room(homes, room_row(owner))
    await add_room(homes, room_row(owner, org))

    assert await counts(homes, TenancyScope(Home.RU, owner, org)) == [2, 2, 2, 2, 2, 2]
    # Комната пространства не видна из личного пространства без членства (inv-14).
    assert await counts(homes, TenancyScope(Home.RU, owner)) == [1, 1, 1, 1, 1, 1]
    # Другой человек того же пространства не видит чужих комнат.
    assert await counts(homes, TenancyScope(Home.RU, other, org)) == [0, 0, 0, 0, 0, 0]
    # Писать за владельца нельзя и в его пространстве.
    with pytest.raises(DBAPIError, match="row-level security"):
        async with homes.transactions.begin(TenancyScope(Home.RU, other, org)) as session:
            session.add(room_row(owner, org))


@pytest.mark.parametrize(
    ("fields", "rule"),
    [
        ({"state": "paused"}, "state_known"),
        ({"state": "closed"}, "closed_with_its_close"),
        ({"closed_by": "owner"}, "closer_with_time"),
        ({"title": ""}, "title_length"),
        ({"invite_token": "short"}, "invite_token_shape"),
        ({"lk_room_name": "room-1"}, "lk_room_name_shape"),
    ],
)
async def test_the_database_keeps_a_rooms_rules(
    homes: DatabaseAccess, fields: dict[str, object], rule: str
) -> None:
    owner = uuid.uuid4()
    with pytest.raises(IntegrityError, match=rule):
        await add_room(homes, room_row(owner, None, **fields), with_kept=False)


async def test_one_call_per_sfu_room_one_seq_per_call_and_one_active_recording(
    homes: DatabaseAccess,
) -> None:
    owner = uuid.uuid4()
    room = await add_room(homes, room_row(owner))
    scope = TenancyScope(Home.RU, owner)
    async with homes.transactions.begin(scope, read_only=True) as session:
        call = await session.scalar(select(RoomCallRecord))
        message = await session.scalar(select(RoomChatMessageRecord))
    assert call is not None
    assert message is not None
    owned = {"room_id": room.id, "owner_id": owner, "org_id": None}
    duplicates = [
        RoomCallRecord(
            id=uuid.uuid4(), lk_room_sid=call.lk_room_sid, started_at=call.started_at,
            ceiling=4, **owned,
        ),
        RoomChatMessageRecord(
            id=uuid.uuid4(), call_id=call.id, owner_id=owner, seq=message.seq,
            principal=message.principal, identity=message.identity, author="Анна", body="Ещё",
        ),
        RoomRecordingRecord(id=uuid.uuid4(), **owned),
    ]  # fmt: skip
    for duplicate in duplicates:
        with pytest.raises(IntegrityError, match="uq_"):
            async with homes.transactions.begin(scope) as session:
                session.add(duplicate)
    async with homes.transactions.begin(scope) as session:
        await session.execute(
            update(RoomRecordingRecord).values(state="complete", ended_at=func.now())
        )
        session.add(RoomRecordingRecord(id=uuid.uuid4(), **owned))


async def test_a_board_is_bounded_and_a_deleted_room_takes_everything(
    homes: DatabaseAccess,
) -> None:
    owner = uuid.uuid4()
    room = await add_room(homes, room_row(owner))
    scope = TenancyScope(Home.RU, owner)
    with pytest.raises(IntegrityError, match="elements_count"):
        async with homes.transactions.begin(scope) as session:
            await session.execute(
                update(RoomWhiteboardRecord).values(elements=[{}] * 20_001, version=1)
            )
    async with homes.transactions.begin(scope) as session:
        await session.execute(delete(RoomRecord).where(RoomRecord.id == room.id))
    assert await counts(homes, scope) == [0, 0, 0, 0, 0, 0]


async def test_the_lookups_answer_one_room_by_its_token_or_livekit_name(
    homes: DatabaseAccess,
) -> None:
    owner, org, stranger = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    room = await add_room(homes, room_row(owner, org), with_kept=False)
    await add_room(homes, room_row(owner), with_kept=False)
    # Вход по ссылке идёт без человека и пространства: функция отвечает только своей комнатой.
    async with homes.transactions.begin(TenancyScope(Home.RU, stranger), read_only=True) as session:
        by_token = (
            await session.execute(
                text("SELECT * FROM meetings_room_by_token(:token)"), {"token": room.invite_token}
            )
        ).all()
        by_name = (
            await session.execute(
                text("SELECT * FROM meetings_room_by_livekit_name(:name)"),
                {"name": room.lk_room_name},
            )
        ).all()
        unknown = (
            await session.execute(text("SELECT * FROM meetings_room_by_token('nosuchtoken000')"))
        ).all()
    assert by_token == by_name == [(room.id, owner, org)]
    assert unknown == []


async def test_the_sweep_role_reads_rooms_calls_and_recordings(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    owner = uuid.uuid4()
    room = await add_room(homes, room_row(owner, uuid.uuid4()))
    shape = ProcessShape(role=ProcessRole.SCHEDULER)
    async with open_database_access(slot_urls(run_slot), shape) as scheduler:
        await scheduler.gate.verify_at_start()
        async with scheduler.transactions.begin(
            TenancyScope(Home.RU), read_only=True, sweep=True
        ) as session:
            seen = [
                await session.scalar(
                    select(func.count()).select_from(model).where(model.room_id == room.id)
                )
                for model in (RoomCallRecord, RoomRecordingRecord)
            ]
            rooms = await session.scalar(select(func.count()).select_from(RoomRecord))
    assert seen == [1, 1]
    assert rooms == 1
