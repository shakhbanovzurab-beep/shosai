"""The room's board over its routes and at the call's end (meetings A11b, MR-D13)."""

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from pydantic_core import to_json
from redis.asyncio import Redis
from sqlalchemy import select

from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.application.written_files import WrittenFilesService
from shosai.features.files.contracts.events import FileUploaded
from shosai.features.files.contracts.written_files import WRITTEN_FILES
from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.meetings.application.board import Boards, scope_of
from shosai.features.meetings.application.handover import CallTask
from shosai.features.meetings.application.passes import PassCheck
from shosai.features.meetings.channels.http.board import build_board_router
from shosai.features.meetings.domain.board import ELEMENTS_BYTES, ELEMENTS_MAX, FILES_BYTES
from shosai.features.meetings.infrastructure.room_passes import RoomPasses
from shosai.features.meetings.infrastructure.room_records import RoomCallRecord
from tests.core.storage.adapters import slot_storage
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.meetings.room_bench import NOW, RoomsBench
from tests.features.meetings.test_chat_api import call_with_two, code_of
from tests.harness.shared_services import SlotBucket

PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(60))
IMAGE = {"img-1": {"id": "img-1", "mimeType": "image/png", "dataURL": "data:image/png;base64,AA"}}


@dataclass(frozen=True, slots=True)
class BoardBench:
    """The board's routes beside the rooms' bench, over the slot's buckets."""

    http: httpx.AsyncClient
    boards: Boards
    check: PassCheck
    rooms: RoomsBench

    async def save(
        self,
        room_id: str,
        room_pass: str,
        elements: Sequence[object],
        *,
        files: Mapping[str, object] | None = None,
        version: int = 0,
    ) -> httpx.Response:
        """A save of a scene with the pass."""
        scene = {"elements": elements, "files": files or {}, "version": version}
        return await self.http.put(
            f"/v1/meetings/rooms/{room_id}/board", json=scene, headers={"X-Room-Pass": room_pass}
        )

    async def picture(self, room_id: str, room_pass: str) -> httpx.Response:
        """A link for the board's PNG."""
        return await self.http.post(
            f"/v1/meetings/rooms/{room_id}/board/picture",
            json={"size_bytes": len(PNG)},
            headers={"X-Room-Pass": room_pass},
        )


@pytest_asyncio.fixture
async def board_bench(
    rooms_bench: RoomsBench, valkey: Redis, buckets: Mapping[Home, SlotBucket]
) -> AsyncIterator[BoardBench]:
    homes, ports = rooms_bench.homes, PortDirectory()
    outbox = EventOutbox(EventTypes([FileUploaded]))
    ports.install(
        [
            ENTITLEMENTS.bind(rooms_bench.people),
            WRITTEN_FILES.bind(WrittenFilesService(homes.transactions, ports, outbox)),
        ]
    )
    objects = {home: slot_storage(bucket).objects for home, bucket in buckets.items()}
    limiter = RateLimiter(valkey, KeyValueMetrics(CollectorRegistry()))
    boards = Boards(homes.transactions, (ports, limiter, objects), lambda: NOW)
    check = PassCheck(homes.transactions, RoomPasses(valkey))
    async with client_of(build_probe_app(extra=(build_board_router(boards, check),)).app) as http:
        yield BoardBench(http, boards, check, rooms_bench)


def element(index: int, version: int = 1) -> dict[str, Any]:
    """An editor's element, as the server never reads it."""
    return {"id": f"el-{index}", "type": "rectangle", "version": version, "x": index}


async def test_a_save_on_the_board_s_version_wins_and_a_stale_one_hears_the_current(
    board_bench: BoardBench,
) -> None:
    room_id, (anna, li) = await call_with_two(board_bench.rooms)
    board = f"/v1/meetings/rooms/{room_id}/board"

    empty = await board_bench.http.get(board, headers={"X-Room-Pass": li})
    first = await board_bench.save(room_id, anna, [element(1)])
    stale = await board_bench.save(room_id, li, [])
    second = await board_bench.save(
        room_id, li, [element(1, 2), element(2)], files=IMAGE, version=1
    )
    after = (await board_bench.http.get(board, headers={"X-Room-Pass": anna})).json()

    assert empty.json() == {"elements": [], "files": {}, "version": 0, "updated_at": None}
    assert (first.json(), second.json()) == ({"version": 1}, {"version": 2})
    assert (stale.status_code, code_of(stale)) == (409, "scene_stale")
    assert stale.json()["error"]["params"] == {"version": 1}
    assert (after["elements"], after["files"], after["version"]) == (
        [element(1, 2), element(2)], IMAGE, 2,
    )  # fmt: skip
    assert after["updated_at"] == NOW.isoformat()


async def test_a_save_needs_a_live_call_its_own_room_and_the_board_s_limits(
    board_bench: BoardBench,
) -> None:
    room_id, (anna, _) = await call_with_two(board_bench.rooms)
    idle_room, (idle_pass, _) = await call_with_two(board_bench.rooms, live=False)
    # Компактный JSON помещается в 4 МиБ, а текст jsonb с пробелами — нет: отвечает граница таблицы.
    wide = {f"k{key:02d}": 0 for key in range(24)}
    spaced = [{"id": f"el-{index}", **wide} for index in range(ELEMENTS_MAX)]
    assert len(to_json(spaced)) < ELEMENTS_BYTES
    many = [element(index) for index in range(ELEMENTS_MAX + 1)]
    heavy = {"img": "x" * FILES_BYTES}

    answers = [
        await board_bench.save(idle_room, idle_pass, []),
        await board_bench.save(idle_room, anna, []),
        await board_bench.save(room_id, anna, many),
        await board_bench.save(room_id, anna, [], files=heavy),
        await board_bench.save(room_id, anna, spaced),
    ]

    assert [(answer.status_code, code_of(answer)) for answer in answers] == [
        (409, "no_live_call"), (404, "room_not_found"), (413, "scene_too_large"),
        (413, "scene_too_large"), (413, "scene_too_large"),
    ]  # fmt: skip


async def test_the_picture_goes_into_the_owner_s_storage_and_lands_in_file_manager_once(
    board_bench: BoardBench,
) -> None:
    room_id, (anna, li) = await call_with_two(board_bench.rooms)

    links = [(await board_bench.picture(room_id, who)).json() for who in (anna, li)]
    async with httpx.AsyncClient() as bucket:
        stored = [
            await bucket.put(link["url"], content=PNG, headers=link["headers"]) for link in links
        ]
    holder = await board_bench.check.holder(anna)
    async with board_bench.rooms.homes.transactions.begin(scope_of(holder)) as session:
        call_id = (
            await session.scalars(
                select(RoomCallRecord.id).where(RoomCallRecord.room_id == holder.room_id)
            )
        ).one()
    task = CallTask(home=Home.RU, user_id=holder.owner_id, call_id=call_id)
    await board_bench.boards.file_picture(task)
    await board_bench.boards.file_picture(task)
    board_bench.rooms.people.file_manager_gb = 0
    full = await board_bench.picture(room_id, anna)

    assert [link["method"] for link in links] == ["PUT", "PUT"]
    assert len({link["url"].split("?")[0] for link in links}) == 1
    assert [answer.status_code for answer in stored] == [200, 200]
    async with board_bench.rooms.homes.transactions.begin(scope_of(holder)) as session:
        files = (await session.scalars(select(StorageFileRecord))).all()
    assert [(item.name, item.size_bytes, item.content_type) for item in files] == [
        ("Meeting 2026-10-27 12-00 board.png", len(PNG), "image/png")
    ]
    assert (full.status_code, code_of(full)) == (413, "storage_limit")
