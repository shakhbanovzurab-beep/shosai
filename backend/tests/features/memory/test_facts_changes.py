"""The person's changes: an edit supersedes once per key, accept, forget, forget everything,
the carried-over list and the switch (memory plan §3.3, step 3); forgetting everything leaves
nothing (MM-D9); each answer to a candidate is counted once, by its source (step 11)."""

import uuid

from redis.asyncio import Redis
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts import Principal
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.infrastructure.metrics import CANDIDATES
from shosai.features.memory.infrastructure.presence import has_memories_key
from shosai.features.memory.infrastructure.records import (
    EMBEDDING_DIMENSIONS as DIMENSIONS,
)
from shosai.features.memory.infrastructure.records import (
    MemoryFactRecord,
    MemoryRefusalRecord,
    MemorySummaryRecord,
)
from tests.features.billing.people_bench import bearer
from tests.features.memory.facts_api_bench import START, FactsBench

URL = "/v1/agent/memory"


async def rows(bench: FactsBench, person: uuid.UUID) -> dict[uuid.UUID, MemoryFactRecord]:
    """Every row of the person, ended ones too."""
    async with bench.homes.transactions.begin(TenancyScope(Home.RU, person), read_only=True) as s:
        return {row.id: row for row in await s.scalars(select(MemoryFactRecord))}


async def traces(bench: FactsBench, person: uuid.UUID) -> int:
    """How many traces of refusals the person has."""
    async with bench.homes.transactions.begin(TenancyScope(Home.RU, person), read_only=True) as s:
        return len(list(await s.scalars(select(MemoryRefusalRecord.id))))


def counted(bench: FactsBench, source: str, answer: str) -> float | None:
    """How many answers of the kind the bench's metrics counted."""
    return bench.registry.get_sample_value(CANDIDATES, {"source": source, "answer": answer})


async def test_an_edit_supersedes_once_per_key_and_keeps_the_pin(facts_bench: FactsBench) -> None:
    person = uuid.uuid4()
    (fact,) = await facts_bench.add(person, [{"statement": "Lives in Moscow", "pinned": True}])
    headers = bearer((Home.RU, person)) | {"Idempotency-Key": "edit-1"}
    body = {"statement": "Lives in Berlin"}

    first = await facts_bench.http.patch(f"{URL}/{fact}", json=body, headers=headers)
    again = await facts_bench.http.patch(f"{URL}/{fact}", json=body, headers=headers)
    reused = await facts_bench.http.patch(f"{URL}/{fact}", json={"statement": "X"}, headers=headers)
    stored = await rows(facts_bench, person)

    edited = first.json()
    assert (edited["statement"], edited["source"]["kind"], edited["pinned"]) == (
        "Lives in Berlin",
        "user_edit",
        True,
    )
    assert edited["id"] != str(fact)
    assert again.json() == edited
    assert reused.json()["error"]["code"] == "idempotency_key_reused"
    old, new = stored[fact], stored[uuid.UUID(edited["id"])]
    assert (old.superseded_by, old.pinned, old.valid_to is not None) == (new.id, False, True)
    assert (new.confirmed, new.explicit, new.source_ref) == (True, True, {"replaced": str(fact)})


async def test_editing_a_candidate_accepts_it_and_a_pin_alone_changes_only_the_pin(
    facts_bench: FactsBench,
) -> None:
    person = uuid.uuid4()
    candidate, fact = await facts_bench.add(
        person, [{"statement": "Waits", "status": "candidate"}, {"statement": "Held"}]
    )
    headers = bearer((Home.RU, person))

    edited = await facts_bench.http.patch(
        f"{URL}/{candidate}",
        json={"statement": "Waited"},
        headers=headers | {"Idempotency-Key": "a"},
    )
    pinned = await facts_bench.http.patch(
        f"{URL}/{fact}", json={"pinned": True}, headers=headers | {"Idempotency-Key": "b"}
    )
    empty = await facts_bench.http.patch(
        f"{URL}/{fact}", json={"statement": "   "}, headers=headers | {"Idempotency-Key": "c"}
    )

    assert (edited.json()["status"], edited.json()["statement"]) == ("active", "Waited")
    assert (pinned.json()["id"], pinned.json()["pinned"]) == (str(fact), True)
    assert (empty.status_code, empty.json()["error"]["code"]) == (422, "memory_fact_invalid")


async def test_accepting_a_candidate_replaces_what_it_proposed_to(facts_bench: FactsBench) -> None:
    person = uuid.uuid4()
    (old,) = await facts_bench.add(person, [{"statement": "Lives in Moscow"}])
    (candidate,) = await facts_bench.add(
        person, [{"statement": "Lives in Berlin", "status": "candidate", "replaces": old}]
    )
    headers = bearer((Home.RU, person))

    accepted = await facts_bench.http.post(f"{URL}/{candidate}/accept", headers=headers)
    again = await facts_bench.http.post(f"{URL}/{candidate}/accept", headers=headers)
    listed = (await facts_bench.http.get(URL, headers=headers)).json()["items"]
    stored = await rows(facts_bench, person)

    assert accepted.json()["status"] == "active"
    assert again.json() == accepted.json()
    assert [item["id"] for item in listed] == [str(candidate)]
    assert stored[old].superseded_by == candidate
    assert stored[candidate].confirmed
    assert counted(facts_bench, "user_statement", "accepted") == 1


async def test_forgetting_is_idempotent_and_never_reaches_another_persons_fact(
    facts_bench: FactsBench,
) -> None:
    person, other = uuid.uuid4(), uuid.uuid4()
    fact, candidate = await facts_bench.add(person, [{}, {"status": "candidate"}])
    (theirs,) = await facts_bench.add(other, [{}])
    headers = bearer((Home.RU, person))

    answers = [
        (await facts_bench.http.delete(f"{URL}/{target}", headers=headers)).status_code
        for target in (fact, fact, candidate, theirs, uuid.uuid4())
    ]
    stored = await rows(facts_bench, person)

    assert answers == [204, 204, 204, 404, 404]
    assert (stored[fact].ended_reason, stored[candidate].ended_reason) == ("forgot", "turned_down")
    assert counted(facts_bench, "user_statement", "turned_down") == 1
    assert (await rows(facts_bench, other))[theirs].status == "active"


async def test_forgetting_everything_deletes_every_fact_trace_and_the_summary(
    facts_bench: FactsBench, valkey: Redis
) -> None:
    person = uuid.uuid4()
    await facts_bench.add(
        person,
        [{}, {"status": "candidate"}, {"source_kind": "imported"},
         {"status": "forgotten", "ended_reason": "forgot", "ended_at": START}],
    )  # fmt: skip
    async with facts_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        session.add(MemorySummaryRecord(user_id=person, language="en"))
        session.add(
            MemoryRefusalRecord(id=uuid.uuid4(), user_id=person, embedding=[1.0] * DIMENSIONS,
                                embedding_model="baai/bge-m3", refused_at=START)
        )  # fmt: skip
    await valkey.set(has_memories_key(person), "1")
    headers = bearer((Home.RU, person))

    done = await facts_bench.http.delete(URL, headers=headers)
    listed = (await facts_bench.http.get(URL, headers=headers)).json()
    async with facts_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        summary = await session.get(MemorySummaryRecord, person)

    assert done.status_code == 204
    assert listed["counts"] == {"active": 0, "candidates": 0, "imported": 0}
    assert await rows(facts_bench, person) == {}
    assert await traces(facts_bench, person) == 0
    assert summary is None
    assert await valkey.exists(has_memories_key(person)) == 0


async def test_the_carried_over_list_is_turned_down_in_one_go(facts_bench: FactsBench) -> None:
    person = uuid.uuid4()
    imported, waiting = await facts_bench.add(
        person,
        [
            {"status": "candidate", "source_kind": "imported"},
            {"status": "candidate"},
        ],
    )
    headers = bearer((Home.RU, person))

    done = await facts_bench.http.post(f"{URL}/imported/turn-down", headers=headers)
    stored = await rows(facts_bench, person)

    assert done.status_code == 204
    assert (stored[imported].ended_reason, stored[waiting].status) == ("turned_down", "candidate")
    assert counted(facts_bench, "imported", "turned_down") == 1


async def test_the_switch_starts_on_keeps_its_moment_and_mirrors_into_the_native_me(
    facts_bench: FactsBench,
) -> None:
    person = uuid.uuid4()
    headers = bearer((Home.RU, person))
    switch = MemorySwitch(facts_bench.homes.transactions)

    before = (await facts_bench.http.get(f"{URL}/settings", headers=headers)).json()
    off = await facts_bench.http.patch(f"{URL}/settings", json={"enabled": False}, headers=headers)
    native = await switch.native_me(Principal(person, Home.RU, 0))
    unknown = await facts_bench.http.patch(f"{URL}/settings", json={"on": True}, headers=headers)

    assert before == {"enabled": True}
    assert off.json() == {"enabled": False}
    assert native == {"memory_enabled": False}
    assert unknown.status_code == 422
