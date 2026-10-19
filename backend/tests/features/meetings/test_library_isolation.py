"""Every route of the library shows each person what §7 allows (meetings step 7a, inv-14).

The isolation kit's canonical world — two workspaces, a member of both, a guest, a private
team, a removed member, a hidden owner, personal meetings shared and not — is written once
per route; each person then asks for every meeting through the route. A meeting they may
not read answers `meeting_not_found`, whatever else the route would say; `PATCH` answers
`meeting_read_only` to a reader who may not manage.
"""

import uuid
from datetime import UTC, datetime

import pytest

from shosai.core.kernel.homes import Home
from shosai.features.meetings.infrastructure.meeting_records import MEETING_RESOURCE
from tests.features.meetings.library_bench import LibraryBench, bearer
from tests.harness.run_slot import RunSlot
from tests.support.access_model import manageable, readable
from tests.support.isolation import Canon, canonical_world, write_world

MEETING_COLUMNS = {"title": "Созвон", "started_at": datetime.now(UTC)}
ROUTES = ("", "/transcript", "/write-up", "/findings", "/map")


async def world(run_slot: RunSlot) -> Canon:
    """The canonical world of meetings in the EU home."""
    canon = canonical_world(MEETING_RESOURCE.kind)
    connection = run_slot.claimed.connections[Home.EU]
    await write_world(connection, MEETING_RESOURCE, canon.world, MEETING_COLUMNS)
    return canon


def meetings(canon: Canon) -> list[uuid.UUID]:
    return [row.id for row in canon.world.rows]


@pytest.mark.isolation(resource="meeting")
@pytest.mark.parametrize("route", ROUTES)
async def test_a_meeting_s_routes_answer_only_those_who_may_read_it(
    library_bench: LibraryBench, run_slot: RunSlot, route: str
) -> None:
    canon = await world(run_slot)

    for name, person in canon.people.items():
        seen = set()
        for meeting_id in meetings(canon):
            answer = await library_bench.get(person, f"/v1/meetings/{meeting_id}{route}")
            code = answer.json().get("error", {}).get("code") if answer.status_code >= 400 else None
            if code != "meeting_not_found":
                seen.add(meeting_id)
        assert seen == readable(canon.world, MEETING_RESOURCE.kind, person), name


@pytest.mark.isolation(resource="meeting")
async def test_the_library_lists_what_each_person_may_read_and_narrows_to_a_workspace(
    library_bench: LibraryBench, run_slot: RunSlot
) -> None:
    canon = await world(run_slot)
    within = canon.workspaces["a"]

    for name, person in canon.people.items():
        listed = await library_bench.every(person, "/v1/meetings", limit=3)
        narrowed = await library_bench.every(person, "/v1/meetings", workspace_id=str(within))
        kind = MEETING_RESOURCE.kind
        assert {uuid.UUID(i["id"]) for i in listed} == readable(canon.world, kind, person), name
        assert {uuid.UUID(i["id"]) for i in narrowed} == readable(
            canon.world, kind, person, within
        ), name


@pytest.mark.isolation(resource="meeting")
async def test_only_those_who_may_manage_a_meeting_rename_it(
    library_bench: LibraryBench, run_slot: RunSlot
) -> None:
    canon = await world(run_slot)
    kind = MEETING_RESOURCE.kind

    for name, person in canon.people.items():
        renamed, read_only = set(), set()
        for meeting_id in meetings(canon):
            answer = await library_bench.http.patch(
                f"/v1/meetings/{meeting_id}", json={"title": "Новое"}, headers=bearer(person)
            )
            if answer.status_code == 200:
                renamed.add(meeting_id)
            elif answer.json()["error"]["code"] == "meeting_read_only":
                read_only.add(meeting_id)
        assert renamed == manageable(canon.world, kind, person), name
        assert read_only == readable(canon.world, kind, person) - renamed, name
