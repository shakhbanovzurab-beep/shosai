"""The owner's own notes and a meeting's participants in the cabinet's shapes (step 7b)."""

import uuid
from http import HTTPStatus

import pytest

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    ParticipantRecord,
)
from tests.features.notes.library_bench import LibraryBench, MeetingSeed, bearer
from tests.features.notes.test_library_isolation import MEETING_COLUMNS
from tests.harness.run_slot import RunSlot
from tests.support.access_model import manageable, readable
from tests.support.isolation import canonical_world, write_world


async def test_a_person_writes_their_own_notes_last_write_wins_and_reads_nobody_else_s(
    library_bench: LibraryBench,
) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    meeting = await library_bench.seed(MeetingSeed(owner))
    path = f"/v1/notes/{meeting.meeting_id}/my-notes"

    before = (await library_bench.get(owner, path)).json()
    first = await library_bench.http.put(path, json={"text": "# Итоги"}, headers=bearer(owner))
    second = await library_bench.http.put(path, json={"text": "- одно"}, headers=bearer(owner))
    after = (await library_bench.get(owner, path)).json()
    long = await library_bench.http.put(path, json={"text": "я" * 50_001}, headers=bearer(owner))
    hidden = await library_bench.get(stranger, path)

    assert before == {"notes": None}
    assert (first.json()["notes"]["version"], second.json()["notes"]["version"]) == (1, 2)
    assert after["notes"] == {
        "text": "- одно", "version": 2, "client": "web",
        "updated_at": after["notes"]["updated_at"],
    }  # fmt: skip
    assert (long.status_code, long.json()["error"]["code"]) == (422, "notes_too_long")
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "meeting_not_found")


async def calendar_participant(
    bench: LibraryBench, owner: uuid.UUID, meeting_id: uuid.UUID
) -> None:
    """A participant the calendar brought, whom no person may remove."""
    async with bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        session.add(
            ParticipantRecord(
                id=uuid.uuid4(), session_id=meeting_id, user_id=owner, name="Календарь",
                email="c@x.io", source="calendar",
            )
        )  # fmt: skip


async def test_participants_are_added_once_by_address_and_only_added_ones_removed(
    library_bench: LibraryBench,
) -> None:
    owner = uuid.uuid4()
    meeting = await library_bench.seed(MeetingSeed(owner))
    await calendar_participant(library_bench, owner, meeting.meeting_id)
    path = f"/v1/notes/{meeting.meeting_id}/participants"
    headers = bearer(owner)

    added = await library_bench.http.post(
        path, json={"email": " Anna@Example.COM ", "name": "Анна"}, headers=headers
    )
    again = await library_bench.http.post(path, json={"email": "anna@example.com"}, headers=headers)
    invalid = await library_bench.http.post(path, json={"email": "anna@"}, headers=headers)
    page = (await library_bench.get(owner, f"/v1/notes/{meeting.meeting_id}")).json()
    calendar = next(p for p in page["participants"] if p["email"] == "c@x.io")
    kept = await library_bench.http.delete(f"{path}/{calendar['id']}", headers=headers)
    removed = await library_bench.http.delete(f"{path}/{added.json()['id']}", headers=headers)
    gone = await library_bench.http.delete(f"{path}/{added.json()['id']}", headers=headers)

    assert added.status_code == HTTPStatus.CREATED
    assert added.json() == {
        "id": added.json()["id"], "name": "Анна", "email": "anna@example.com", "source": "added",
    }  # fmt: skip
    assert (again.status_code, again.json()["id"]) == (200, added.json()["id"])
    assert invalid.json()["error"]["code"] == "participant_email_invalid"
    assert (kept.status_code, kept.json()["error"]["code"]) == (409, "participant_not_removable")
    assert removed.status_code == HTTPStatus.NO_CONTENT
    assert (gone.status_code, gone.json()["error"]["code"]) == (404, "participant_not_found")


async def test_a_meeting_takes_at_most_a_hundred_participants(library_bench: LibraryBench) -> None:
    owner = uuid.uuid4()
    meeting = await library_bench.seed(MeetingSeed(owner))
    async with library_bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        session.add_all(
            ParticipantRecord(
                id=uuid.uuid4(), session_id=meeting.meeting_id, user_id=owner,
                email=f"p{n}@x.io", source="calendar",
            )
            for n in range(100)
        )  # fmt: skip

    refused = await library_bench.http.post(
        f"/v1/notes/{meeting.meeting_id}/participants",
        json={"email": "one-more@x.io"},
        headers=bearer(owner),
    )

    assert (refused.status_code, refused.json()["error"]["code"]) == (
        409, "participants_limit_reached",
    )  # fmt: skip


@pytest.mark.isolation(resource="meeting")
async def test_everyone_who_may_read_keeps_notes_of_their_own_that_nobody_else_sees(
    library_bench: LibraryBench, run_slot: RunSlot
) -> None:
    canon = canonical_world(MEETING_RESOURCE.kind)
    await write_world(
        run_slot.claimed.connections[Home.EU], MEETING_RESOURCE, canon.world, MEETING_COLUMNS
    )
    kind = MEETING_RESOURCE.kind

    for name, person in canon.people.items():
        written = set()
        for row in canon.world.rows:
            answer = await library_bench.http.put(
                f"/v1/notes/{row.id}/my-notes", json={"text": name}, headers=bearer(person)
            )
            if answer.status_code == HTTPStatus.OK:
                written.add(row.id)
        assert written == readable(canon.world, kind, person), name
    for name, person in canon.people.items():
        for row_id in readable(canon.world, kind, person):
            notes = (await library_bench.get(person, f"/v1/notes/{row_id}/my-notes")).json()
            assert notes["notes"]["text"] == name, name


@pytest.mark.isolation(resource="meeting")
async def test_participants_change_only_for_those_who_may_manage(
    library_bench: LibraryBench, run_slot: RunSlot
) -> None:
    canon = canonical_world(MEETING_RESOURCE.kind)
    await write_world(
        run_slot.claimed.connections[Home.EU], MEETING_RESOURCE, canon.world, MEETING_COLUMNS
    )

    for name, person in canon.people.items():
        people = set()
        for row in canon.world.rows:
            added = await library_bench.http.post(
                f"/v1/notes/{row.id}/participants",
                json={"email": f"{name}@x.io"},
                headers=bearer(person),
            )
            if added.status_code == HTTPStatus.CREATED:
                people.add(row.id)
        assert people == manageable(canon.world, MEETING_RESOURCE.kind, person), name
