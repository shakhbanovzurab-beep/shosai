"""A person's folders and templates, and a meeting's template choice (notes step 7b)."""

import asyncio
import uuid
from http import HTTPStatus
from typing import Any

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.infrastructure.meeting_records import MEETING_RESOURCE
from shosai.features.notes.infrastructure.notes_records import TemplateRecord
from tests.features.notes.library_bench import LibraryBench, MeetingSeed, bearer
from tests.features.notes.test_library_isolation import MEETING_COLUMNS
from tests.harness.run_slot import RunSlot
from tests.support.isolation import canonical_world, write_world

OWN = {
    "name": "Клиент", "description": "Звонок с клиентом", "icon": "phone",
    "sections": [{"kind": "action_items", "title": "Дальше"}, {"kind": "summary"}],
}  # fmt: skip


async def test_folders_take_colours_in_turn_and_their_meetings_survive_them(
    library_bench: LibraryBench,
) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    http, headers = library_bench.http, bearer(owner)
    first = await http.post(
        "/v1/notes/folders",
        json={"name": "Клиенты"},
        headers={**headers, "Idempotency-Key": "f1"},
    )
    replay = await http.post(
        "/v1/notes/folders",
        json={"name": "Клиенты"},
        headers={**headers, "Idempotency-Key": "f1"},
    )
    reused = await http.post(
        "/v1/notes/folders",
        json={"name": "Другое"},
        headers={**headers, "Idempotency-Key": "f1"},
    )
    second = await http.post("/v1/notes/folders", json={"name": "Команда"}, headers=headers)
    long = await http.post("/v1/notes/folders", json={"name": "я" * 41}, headers=headers)
    folder = first.json()["id"]
    renamed = await http.patch(
        f"/v1/notes/folders/{folder}", json={"name": "Партнёры"}, headers=headers
    )
    foreign = await http.patch(
        f"/v1/notes/folders/{folder}", json={"name": "Моё"}, headers=bearer(stranger)
    )
    listed = await library_bench.every(owner, "/v1/notes/folders", limit=1)
    filed = await library_bench.seed(MeetingSeed(owner, folder_id=uuid.UUID(folder)))
    deleted = await http.delete(f"/v1/notes/folders/{folder}", headers=headers)
    after = (await library_bench.get(owner, f"/v1/notes/{filed.meeting_id}")).json()

    assert (first.status_code, first.json()["color"]) == (201, "green")
    assert replay.json() == first.json()
    assert reused.json()["error"]["code"] == "idempotency_key_reused"
    assert second.json()["color"] == "violet"
    assert (long.status_code, long.json()["error"]["code"]) == (422, "folder_name_too_long")
    assert renamed.json()["name"] == "Партнёры"
    assert (foreign.status_code, foreign.json()["error"]["code"]) == (404, "folder_not_found")
    assert [f["name"] for f in listed] == ["Партнёры", "Команда"]
    assert deleted.status_code == HTTPStatus.NO_CONTENT
    assert after["folder_id"] is None


async def test_shipped_templates_are_read_only_and_a_person_keeps_at_most_fifty(
    library_bench: LibraryBench,
) -> None:
    owner = uuid.uuid4()
    http, headers = library_bench.http, bearer(owner)

    made = await http.post("/v1/notes/templates", json=OWN, headers=headers)
    unknown = await http.post(
        "/v1/notes/templates",
        json={**OWN, "sections": [{"kind": "jokes"}]},
        headers=headers,
    )
    replaced = await http.put(
        f"/v1/notes/templates/{made.json()['id']}",
        json={**OWN, "name": "Клиент, коротко", "sections": [{"kind": "summary"}]},
        headers=headers,
    )
    shipped_put = await http.put("/v1/notes/templates/oneOnOne", json=OWN, headers=headers)
    shipped_delete = await http.delete("/v1/notes/templates/oneOnOne", headers=headers)
    listed = (await library_bench.get(owner, "/v1/notes/templates")).json()
    await many_templates(library_bench, owner, 49)
    over = await http.post("/v1/notes/templates", json=OWN, headers=headers)
    removed = await http.delete(f"/v1/notes/templates/{made.json()['id']}", headers=headers)

    assert made.status_code == HTTPStatus.CREATED
    assert made.json()["sections"] == [
        {"kind": "summary", "heading_code": "summary", "title": None},
        {"kind": "action_items", "heading_code": None, "title": "Дальше"},
    ]
    assert unknown.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert replaced.json()["name"] == "Клиент, коротко"
    assert shipped_put.json()["error"]["code"] == "template_builtin_read_only"
    assert shipped_delete.status_code == HTTPStatus.CONFLICT
    assert listed["next_cursor"] is None
    assert [t["id"] for t in listed["items"][:2]] == ["enhanced", "catchUpInvestor"]
    assert listed["items"][1] == {
        "id": "catchUpInvestor", "builtin": True, "name": None, "description": None,
        "icon": "handshake", "sections": listed["items"][1]["sections"],
    }  # fmt: skip
    assert len(listed["items"]) == 10
    assert (over.status_code, over.json()["error"]["code"]) == (409, "templates_limit_reached")
    assert removed.status_code == HTTPStatus.NO_CONTENT


async def many_templates(bench: LibraryBench, owner: uuid.UUID, count: int) -> None:
    """Templates of the person's, written straight to the table."""
    sections: list[dict[str, Any]] = [{"kind": "summary", "title": None}]
    async with bench.homes.transactions.begin(TenancyScope(Home.EU, owner)) as session:
        session.add_all(
            TemplateRecord(
                id=uuid.uuid4(), user_id=owner, name=f"Шаблон {n}", icon="chart", sections=sections
            )
            for n in range(count)
        )


async def test_the_owner_chooses_their_template_and_another_manager_only_a_shipped_one(
    library_bench: LibraryBench, run_slot: RunSlot
) -> None:
    canon = canonical_world(MEETING_RESOURCE.kind)
    await write_world(
        run_slot.claimed.connections[Home.EU], MEETING_RESOURCE, canon.world, MEETING_COLUMNS
    )
    alice, bob = canon.people["alice"], canon.people["bob"]
    [bobs] = [
        row.id
        for row in canon.world.rows
        if row.owner == bob and row.org_id is not None and row.access == "organization"
    ]
    http = library_bench.http
    alices = (await http.post("/v1/notes/templates", json=OWN, headers=bearer(alice))).json()
    bobs_own = (await http.post("/v1/notes/templates", json=OWN, headers=bearer(bob))).json()
    path = f"/v1/notes/{bobs}"

    foreign = await http.patch(path, json={"template_id": alices["id"]}, headers=bearer(alice))
    shipped = await http.patch(path, json={"template_id": "teamSync"}, headers=bearer(alice))
    by_owner = await http.patch(path, json={"template_id": bobs_own["id"]}, headers=bearer(bob))
    missing = await http.patch(path, json={"template_id": str(uuid.uuid4())}, headers=bearer(bob))
    cleared = await http.patch(path, json={"template_id": None}, headers=bearer(bob))

    assert (foreign.status_code, foreign.json()["error"]["code"]) == (409, "template_not_shipped")
    assert shipped.json()["template_id"] == "teamSync"
    assert by_owner.json()["template_id"] == bobs_own["id"]
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "template_not_found")
    assert cleared.json()["template_id"] is None


async def test_two_creates_at_once_never_take_a_person_past_fifty(
    library_bench: LibraryBench,
) -> None:
    owner = uuid.uuid4()
    await many_templates(library_bench, owner, 49)

    answers = await asyncio.gather(
        *(
            library_bench.http.post("/v1/notes/templates", json=OWN, headers=bearer(owner))
            for _ in range(2)
        )
    )

    assert sorted(answer.status_code for answer in answers) == [201, 409]
