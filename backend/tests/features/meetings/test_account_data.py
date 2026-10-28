"""Meetings' part of a person's export, transfer and erasure (ADR 0045 point 7, nfr-16)."""

import json
import uuid
from typing import Any

from sqlalchemy import select

from shosai.core.account_data.handlers import AccountRef
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.application.account_data import PERSONAL_ROWS, MeetingsAccountData
from shosai.features.meetings.infrastructure.room_records import RoomRecord
from tests.features.meetings.room_kit import add_broadcast, add_room, room_row
from tests.harness.database_access import DatabaseAccess


async def exported(
    handler: MeetingsAccountData, account: AccountRef
) -> dict[str, list[dict[str, Any]]]:
    """Every file of the export, as its rows."""
    files: dict[str, list[dict[str, Any]]] = {}
    async for item in handler.export(account):
        lines = b"".join([chunk async for chunk in item.chunks]).decode().splitlines()
        files[item.name] = [json.loads(line) for line in lines]
    return files


async def test_personal_rooms_are_exported_moved_and_erased_and_a_workspaces_stay(
    homes: DatabaseAccess,
) -> None:
    person, org = uuid.uuid4(), uuid.uuid4()
    personal = await add_room(homes, room_row(person, None, title="Планёрка"))
    workspace = await add_room(homes, room_row(person, org))
    for room in (personal, workspace):
        await add_broadcast(homes, room)
    handler = MeetingsAccountData(homes.transactions)
    russian, european = AccountRef(person, Home.RU), AccountRef(person, Home.EU)

    files = await exported(handler, russian)
    assert set(files) == {f"{rows.table.name}.jsonl" for rows in PERSONAL_ROWS}
    assert [(room["id"], room["title"]) for room in files["rooms.jsonl"]] == [
        (str(personal.id), "Планёрка")
    ]
    assert all(len(rows) == 1 for rows in files.values())

    await handler.copy(russian, Home.EU)
    await handler.copy(russian, Home.EU)
    assert await handler.manifest(european) == await handler.manifest(russian)

    await handler.erase(russian)
    await handler.erase(russian)
    assert await handler.remains(russian) == ()
    assert await handler.remains(european) != ()
    await handler.purge(european)
    assert await handler.remains(european) == ()
    # Комната пространства остаётся пространству: её снимает объявление пространства.
    scope = TenancyScope(Home.RU, person, org)
    async with homes.transactions.begin(scope, read_only=True) as session:
        kept = (await session.scalars(select(RoomRecord.id))).all()
    assert kept == [workspace.id]
