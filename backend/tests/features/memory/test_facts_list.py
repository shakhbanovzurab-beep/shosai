"""The list of what Leo remembers: order, counts, filters on the server, pages, and what the
person may see (memory plan §3.3, step 3)."""

import uuid

from shosai.core.kernel.homes import Home
from tests.features.billing.people_bench import bearer
from tests.features.memory.facts_api_bench import START, FactsBench

URL = "/v1/agent/memory"


async def test_candidates_come_first_and_the_counts_cover_every_page(
    facts_bench: FactsBench,
) -> None:
    person = uuid.uuid4()
    old, candidate, new, imported, forgotten = await facts_bench.add(
        person,
        [
            {"statement": "Old fact"},
            {"statement": "Waits", "status": "candidate"},
            {"statement": "New fact", "kind": "goal"},
            {"statement": "From the draft", "status": "candidate", "source_kind": "imported"},
            {"status": "forgotten", "ended_reason": "forgot", "ended_at": START},
        ],
    )
    headers = bearer((Home.RU, person))

    first = (await facts_bench.http.get(URL, params={"limit": 2}, headers=headers)).json()
    second = (
        await facts_bench.http.get(
            URL, params={"limit": 2, "cursor": first["next_cursor"]}, headers=headers
        )
    ).json()
    carried = (
        await facts_bench.http.get(URL, params={"source": "imported"}, headers=headers)
    ).json()
    goals = (await facts_bench.http.get(URL, params={"kind": "goal"}, headers=headers)).json()
    found = (await facts_bench.http.get(URL, params={"q": "OLD"}, headers=headers)).json()
    waiting = (
        await facts_bench.http.get(URL, params={"status": "candidate"}, headers=headers)
    ).json()

    assert [item["id"] for item in first["items"] + second["items"]] == [
        str(candidate),
        str(new),
        str(old),
    ]
    assert second["next_cursor"] is None
    assert first["counts"] == {"active": 2, "candidates": 1, "imported": 1}
    assert [item["id"] for item in carried["items"]] == [str(imported)]
    assert [item["id"] for item in goals["items"]] == [str(new)]
    assert [item["id"] for item in found["items"]] == [str(old)]
    assert [item["id"] for item in waiting["items"]] == [str(candidate)]
    assert str(forgotten) not in {item["id"] for item in first["items"] + second["items"]}
    assert first["items"][0] == {
        "id": str(candidate), "kind": "fact", "statement": "Waits", "status": "candidate",
        "pinned": False, "created_at": first["items"][0]["created_at"],
        "source": {"kind": "user_statement", "title": None, "thread_id": None, "message_id": None},
    }  # fmt: skip


async def test_a_workspaces_fact_is_seen_only_while_the_person_is_in_it(
    facts_bench: FactsBench,
) -> None:
    person, org = uuid.uuid4(), uuid.uuid4()
    (fact,) = await facts_bench.add(person, [{"org_id": org}])
    headers = bearer((Home.RU, person))

    outside = (await facts_bench.http.get(URL, headers=headers)).json()
    facts_bench.spaces.of[person] = {org}
    inside = (await facts_bench.http.get(URL, headers=headers)).json()
    leaving = await facts_bench.http.delete(f"{URL}/{fact}", headers={**headers})
    facts_bench.spaces.of[person] = set()
    after = await facts_bench.http.delete(f"{URL}/{fact}", headers=headers)

    assert outside["items"] == []
    assert outside["counts"]["active"] == 0
    assert [item["id"] for item in inside["items"]] == [str(fact)]
    assert leaving.status_code == 204
    # Забытый факт — уже ответ «готово», даже без членства.
    assert after.status_code == 204


async def test_a_meetings_fact_names_the_meeting_as_titled_now(facts_bench: FactsBench) -> None:
    person, meeting, gone = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    facts_bench.meetings.titles[meeting] = "Northwind pricing call"
    await facts_bench.add(
        person,
        [
            {"source_kind": "meeting", "source_ref": {"meeting_id": str(meeting)}},
            {"source_kind": "meeting", "source_ref": {"meeting_id": str(gone)}},
            {"thread_id": meeting, "source_ref": {"message_id": str(gone)}},
        ],
    )

    items = (await facts_bench.http.get(URL, headers=bearer((Home.RU, person)))).json()["items"]

    sources = [item["source"] for item in reversed(items)]
    assert sources[0]["title"] == "Northwind pricing call"
    assert sources[1]["title"] is None
    assert (sources[2]["thread_id"], sources[2]["message_id"]) == (str(meeting), str(gone))


async def test_another_persons_facts_are_never_listed_and_a_bad_cursor_is_refused(
    facts_bench: FactsBench,
) -> None:
    person, other = uuid.uuid4(), uuid.uuid4()
    await facts_bench.add(other, [{"statement": "Someone else's"}])
    headers = bearer((Home.RU, person))

    seen = (await facts_bench.http.get(URL, headers=headers)).json()
    broken = await facts_bench.http.get(URL, params={"cursor": "nope"}, headers=headers)
    unknown = await facts_bench.http.get(URL, params={"status": "forgotten"}, headers=headers)

    assert seen == {
        "items": [],
        "next_cursor": None,
        "counts": {"active": 0, "candidates": 0, "imported": 0},
    }
    assert (broken.status_code, broken.json()["error"]["code"]) == (422, "invalid_cursor")
    assert unknown.status_code == 422
