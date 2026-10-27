"""Removing someone for good, lowering a hand, and a person's rooms closing with their account
(meetings A4, §3.6)."""

import uuid

import httpx
from sqlalchemy import select

from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.application.account_rooms import AccountRooms
from shosai.features.meetings.infrastructure.room_records import RoomRecord
from tests.features.meetings.room_bench import NOW, RoomsBench
from tests.harness.database_access import ProcessShape, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot


def code_of(answer: httpx.Response) -> str:
    """The error's code in the platform's envelope."""
    return str(answer.json()["error"]["code"])


async def open_room(
    bench: RoomsBench, owner: uuid.UUID, workspace: uuid.UUID | None = None
) -> tuple[str, str]:
    """A room of the owner: its id and its invitation token."""
    headers = {**bench.bearer(owner), "Idempotency-Key": uuid.uuid4().hex}
    body = {} if workspace is None else {"workspace_id": str(workspace)}
    room = (await bench.http.post("/v1/meetings/rooms", json=body, headers=headers)).json()
    return str(room["id"]), str(room["link"]).rsplit("/", 1)[1]


async def test_a_removed_person_leaves_on_every_device_and_cannot_return(
    rooms_bench: RoomsBench,
) -> None:
    owner, person = uuid.uuid4(), uuid.uuid4()
    rooms_bench.people.named[person] = "Пётр"
    room_id, token = await open_room(rooms_bench, owner)
    join = f"/v1/meetings/join/{token}"
    phone = (await rooms_bench.http.post(join, json={}, headers=rooms_bench.bearer(person))).json()
    laptop = (await rooms_bench.http.post(join, json={}, headers=rooms_bench.bearer(person))).json()
    guest = (await rooms_bench.http.post(join, json={"name": "Гость"})).json()
    name = next(iter(rooms_bench.sfu.rooms_held))
    rooms_bench.sfu.seat(name, [phone["identity"], laptop["identity"], guest["identity"]])
    path = f"/v1/meetings/rooms/{room_id}/participants/{phone['identity']}"

    stranger = await rooms_bench.http.delete(path, headers=rooms_bench.bearer(uuid.uuid4()))
    removed = await rooms_bench.http.delete(path, headers=rooms_bench.bearer(owner))
    again = await rooms_bench.http.delete(path, headers=rooms_bench.bearer(owner))
    back = await rooms_bench.http.post(join, json={}, headers=rooms_bench.bearer(person))
    renewal = await rooms_bench.http.post(
        "/v1/meetings/passes/refresh", headers={"X-Room-Pass": laptop["room_pass"]}
    )

    assert (stranger.status_code, code_of(stranger)) == (404, "room_not_found")
    assert (removed.status_code, again.status_code) == (204, 204)
    assert [item.identity for item in rooms_bench.sfu.sessions[name]] == [guest["identity"]]
    assert (back.status_code, code_of(back)) == (403, "removed")
    assert (renewal.status_code, code_of(renewal)) == (401, "room_pass_invalid")


async def test_the_owner_cannot_remove_themselves_nor_an_identity_shosai_did_not_mint(
    rooms_bench: RoomsBench,
) -> None:
    owner = uuid.uuid4()
    rooms_bench.people.named[owner] = "Анна"
    room_id, token = await open_room(rooms_bench, owner)
    mine = (
        await rooms_bench.http.post(
            f"/v1/meetings/join/{token}", json={}, headers=rooms_bench.bearer(owner)
        )
    ).json()
    base = f"/v1/meetings/rooms/{room_id}/participants"

    myself = await rooms_bench.http.delete(
        f"{base}/{mine['identity']}", headers=rooms_bench.bearer(owner)
    )
    egress = await rooms_bench.http.delete(f"{base}/EG_abc", headers=rooms_bench.bearer(owner))

    assert (myself.status_code, code_of(myself)) == (409, "cannot_remove_owner")
    assert (egress.status_code, code_of(egress)) == (404, "participant_not_found")


async def test_the_owner_lowers_a_raised_hand(rooms_bench: RoomsBench) -> None:
    owner = uuid.uuid4()
    room_id, token = await open_room(rooms_bench, owner)
    guest = (
        await rooms_bench.http.post(f"/v1/meetings/join/{token}", json={"name": "Гость"})
    ).json()
    name = next(iter(rooms_bench.sfu.rooms_held))
    rooms_bench.sfu.seat(name, [guest["identity"]])
    await rooms_bench.sfu.set_attributes(name, guest["identity"], {"hand": NOW.isoformat()})
    path = f"/v1/meetings/rooms/{room_id}/participants/{guest['identity']}/hand"

    lowered = await rooms_bench.http.patch(
        path, json={"raised": False}, headers=rooms_bench.bearer(owner)
    )
    raised = await rooms_bench.http.patch(
        path, json={"raised": True}, headers=rooms_bench.bearer(owner)
    )
    gone = await rooms_bench.http.patch(
        f"/v1/meetings/rooms/{room_id}/participants/guest-0123456789ab__0a1b2c3d/hand",
        json={"raised": False},
        headers=rooms_bench.bearer(owner),
    )

    assert lowered.status_code == 204
    assert "hand" not in rooms_bench.sfu.sessions[name][0].attributes
    assert raised.status_code == 422
    assert (gone.status_code, code_of(gone)) == (404, "participant_not_found")


async def test_a_deleted_or_blocked_accounts_rooms_close_and_their_links_say_not_found(
    rooms_bench: RoomsBench, run_slot: RunSlot
) -> None:
    owner, org = uuid.uuid4(), uuid.uuid4()
    rooms_bench.spaces.of[owner] = {org}
    personal, token = await open_room(rooms_bench, owner)
    workspace, _ = await open_room(rooms_bench, owner, org)
    await rooms_bench.http.post(f"/v1/meetings/join/{token}", json={"name": "Гость"})

    shape = ProcessShape(role=ProcessRole.WORKERS)
    async with open_database_access(slot_urls(run_slot), shape) as workers:
        await workers.gate.verify_at_start()
        rooms = AccountRooms(workers.transactions, rooms_bench.sfu, lambda: NOW)
        closed = await rooms.close_all(Home.RU, owner)
        again = await rooms.close_all(Home.RU, owner)
    join = await rooms_bench.http.post(f"/v1/meetings/join/{token}", json={"name": "Гость"})

    assert (closed, again) == (2, 0)
    assert (join.status_code, code_of(join)) == (404, "not_found")
    assert len(set(rooms_bench.sfu.deleted)) == 2
    for room_id, space in ((personal, None), (workspace, org)):
        scope = TenancyScope(Home.RU, owner, space)
        async with rooms_bench.homes.transactions.begin(scope, read_only=True) as session:
            row = await session.scalar(
                select(RoomRecord).where(RoomRecord.id == uuid.UUID(room_id))
            )
        assert row is not None
        assert (row.state, row.closed_by) == ("closed", "account")
