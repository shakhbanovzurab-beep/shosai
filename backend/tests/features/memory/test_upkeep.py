"""Memory's upkeep, departures and invariant: the pass is idempotent per day and home, faded facts
and unanswered candidates expire but the draft's never do, ended rows go after their day and
traces older than 90 days are dropped (MM-D9), a left workspace's facts vanish and are erased
after 7 days unless the person is back, a deleted workspace's go at once, a deleted meeting's
hide and return with it, and a fact written while memory is off is counted (memory step 8,
MM-D4)."""

import uuid
from datetime import timedelta

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.contracts import Principal
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.application.upkeep import cursor_key
from shosai.features.memory.infrastructure.metrics import CANDIDATES, SummaryTrigger
from tests.features.memory.recall_bench import MODEL, axis
from tests.features.memory.upkeep_bench import NOW, UpkeepBench

LONG_AGO = NOW - timedelta(days=200)
GONE = NOW - timedelta(days=181)


async def test_the_daily_pass_expires_deletes_traces_and_queues_once_a_day(
    upkeep_bench: UpkeepBench,
) -> None:
    person = uuid.uuid4()
    await upkeep_bench.valkey.delete(cursor_key(Home.RU, NOW.date().isoformat()))
    old_trace = await upkeep_bench.trace(person, NOW - timedelta(days=91))
    lately, *_ = await upkeep_bench.add(
        person,
        [{"statement": "Forgotten lately", "status": "forgotten", "ended_reason": "forgot",
          "ended_at": NOW - timedelta(days=10), "embedding": axis(1), "embedding_model": MODEL}],
    )  # fmt: skip
    await upkeep_bench.add(
        person,
        [
            {"statement": "Faded goal", "kind": "goal", "last_confirmed_at": LONG_AGO},
            {"statement": "Pinned goal", "kind": "goal", "last_confirmed_at": LONG_AGO,
             "pinned": True},
            {"statement": "Fresh"},
            {"statement": "Old guess", "status": "candidate", "confirmed": False,
             "created_at": NOW - timedelta(days=31)},
            {"statement": "Carried over", "status": "candidate", "confirmed": False,
             "source_kind": "imported", "created_at": LONG_AGO},
            {"statement": "Forgotten long ago", "status": "forgotten", "ended_reason": "forgot",
             "ended_at": GONE},
            {"statement": "Replaced long ago", "valid_to": GONE, "superseded_by": uuid.uuid4()},
            {"statement": "Forgotten an hour ago", "status": "forgotten", "ended_reason": "forgot",
             "ended_at": NOW - timedelta(hours=1)},
        ],
    )  # fmt: skip

    first = await upkeep_bench.upkeep.run(Home.RU)
    again = await upkeep_bench.upkeep.run(Home.RU)
    tended = await upkeep_bench.upkeep.tend(TenancyScope(Home.RU, person))
    rows = await upkeep_bench.rows(person)

    assert first >= 1
    assert again == 0
    assert (tended.expired, tended.purged) == (0, 0)
    assert {name: (row.status, row.ended_reason) for name, row in rows.items()} == {
        "Faded goal": ("forgotten", "expired"), "Pinned goal": ("active", None),
        "Fresh": ("active", None), "Old guess": ("forgotten", "expired"),
        "Carried over": ("candidate", None), "Forgotten an hour ago": ("forgotten", "forgot"),
    }  # fmt: skip
    assert await upkeep_bench.traces(person) == {lately}
    assert old_trace not in await upkeep_bench.traces(person)
    assert (TenancyScope(Home.RU, person), SummaryTrigger.UPKEEP) in upkeep_bench.queued
    expired = {"source": "user_statement", "answer": "expired"}
    assert upkeep_bench.registry.get_sample_value(CANDIDATES, expired) == 1


async def test_a_left_workspace_s_facts_are_erased_after_a_week_unless_the_person_is_back(
    upkeep_bench: UpkeepBench,
) -> None:
    leaver, returner, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await upkeep_bench.add(leaver, [{"statement": "Team's", "org_id": org}, {"statement": "Own"}])
    await upkeep_bench.add(returner, [{"statement": "Team's", "org_id": org}])
    for person in (leaver, returner):
        async with upkeep_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as s:
            await upkeep_bench.departures.left(s, person, org, NOW - timedelta(days=8))
    upkeep_bench.spaces.of[returner] = {org}

    await upkeep_bench.departures.settle(Home.RU)
    left, back = await upkeep_bench.rows(leaver), await upkeep_bench.rows(returner)

    assert set(left) == {"Own"}
    assert left["Own"].erase_after is None
    assert back["Team's"].erase_after is None


async def test_a_member_again_by_the_delivery_is_not_marked_and_a_deleted_workspace_goes(
    upkeep_bench: UpkeepBench,
) -> None:
    person, org = uuid.uuid4(), uuid.uuid4()
    await upkeep_bench.add(person, [{"statement": "Team's", "org_id": org}, {"statement": "Own"}])
    upkeep_bench.spaces.of[person] = {org}
    async with upkeep_bench.homes.transactions.begin(TenancyScope(Home.RU, person)) as session:
        await upkeep_bench.departures.left(session, person, org, NOW)
    marked = (await upkeep_bench.rows(person))["Team's"].erase_after

    erased = await upkeep_bench.departures.workspace_deleted(Home.RU, org)

    assert marked is None
    assert erased == 1
    assert set(await upkeep_bench.rows(person)) == {"Own"}


async def test_a_deleted_meeting_s_facts_hide_and_return_with_it(
    upkeep_bench: UpkeepBench,
) -> None:
    first, second, meeting, purged = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    heard = {"source_kind": "meeting", "confirmed": False, "source_taint": "external"}
    for person in (first, second):
        await upkeep_bench.add(
            person,
            [{"statement": "Heard", "source_ref": {"meeting_id": str(meeting)}} | heard,
             {"statement": "Heard elsewhere", "source_ref": {"meeting_id": str(purged)}} | heard],
        )  # fmt: skip

    await upkeep_bench.departures.meeting_deleted(Home.RU, meeting, NOW)
    await upkeep_bench.departures.meeting_deleted(Home.RU, purged, NOW - timedelta(days=8))
    hidden = await upkeep_bench.rows(first)
    upkeep_bench.meetings.titles[meeting] = "Design review"
    await upkeep_bench.departures.meeting_restored(Home.RU, meeting)
    await upkeep_bench.departures.settle(Home.RU)

    assert hidden["Heard"].erase_after is not None
    for person in (first, second):
        rows = await upkeep_bench.rows(person)
        assert set(rows) == {"Heard"}
        assert rows["Heard"].erase_after is None


async def test_a_fact_written_by_a_writer_while_memory_is_off_is_counted(
    upkeep_bench: UpkeepBench,
) -> None:
    person = uuid.uuid4()
    # Момент выключения — тот же NOW, что у фактов: в долгом прогоне часы ушли бы вперёд.
    await MemorySwitch(upkeep_bench.homes.transactions, lambda: NOW).turn(
        Principal(person, Home.RU, 0), enabled=False
    )
    before = await upkeep_bench.invariants.check(Home.RU)
    later = NOW + timedelta(minutes=1)
    await upkeep_bench.add(
        person,
        [{"statement": "Admitted", "created_at": later},
         {"statement": "Edited", "source_kind": "user_edit", "created_at": later}],
    )  # fmt: skip

    after = await upkeep_bench.invariants.check(Home.RU)

    assert after == before + 1
