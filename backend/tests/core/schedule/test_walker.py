"""The walk queues each due job once per interval in each home, whatever the races (§12).

Two walkers stand for two scheduler processes; a new walker stands for a restart. The
sender is a recording double: the walk's contract with Valkey is `send_tick`.
"""

import asyncio
from datetime import timedelta

import pytest
from prometheus_client import CollectorRegistry

from shosai.core.kernel.homes import Home
from shosai.core.schedule.metrics import ScheduleMetrics
from shosai.core.schedule.walker import ScheduleWalker, WalkResult
from tests.core.schedule.jobs_bench import DAILY_EU, HOURLY, RecordingTicks
from tests.harness.connections import Connection, fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

JOBS = (HOURLY, DAILY_EU)


def walker(
    homes: DatabaseAccess, ticks: RecordingTicks, registry: CollectorRegistry | None = None
) -> ScheduleWalker:
    """One scheduler process's walk over the probe jobs."""
    metrics = ScheduleMetrics(registry or CollectorRegistry())
    return ScheduleWalker(homes.transactions, ticks, metrics, JOBS)


async def runs(connection: Connection) -> dict[str, bool]:
    """Each job row of a home and whether it has run."""
    rows = await fetch_rows(
        connection, "SELECT job_name, last_run_at IS NOT NULL AS ran FROM schedule_runs"
    )
    return {row["job_name"]: row["ran"] for row in rows}


async def test_two_racing_walks_queue_each_job_once_per_interval_in_each_home(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    ticks = RecordingTicks()
    first, second = walker(homes, ticks), walker(homes, ticks)

    for home in Home:
        await asyncio.gather(first.walk(home), second.walk(home))
        await asyncio.gather(first.walk(home), second.walk(home))

    assert sorted(ticks.sent) == [
        (DAILY_EU.name, "eu"),
        (HOURLY.name, "eu"),
        (HOURLY.name, "ru"),
    ]
    assert await runs(run_slot.claimed.connections[Home.RU]) == {HOURLY.name: True}


async def test_a_missed_interval_runs_once_after_a_restart(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    ticks = RecordingTicks()
    await walker(homes, ticks).walk(Home.RU)
    connection = run_slot.claimed.connections[Home.RU]
    await connection.execute("UPDATE schedule_runs SET last_run_at = now() - interval '5 hours'")

    restarted = walker(homes, ticks)
    after_restart = await restarted.walk(Home.RU)
    again = await restarted.walk(Home.RU)

    assert after_restart == WalkResult(queued=[HOURLY.name])
    assert again == WalkResult()
    assert ticks.sent.count((HOURLY.name, "ru")) == 2


async def test_a_job_that_could_not_be_queued_gives_its_claim_back(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    registry = CollectorRegistry()
    failing = RecordingTicks(failing={HOURLY.name})

    failed = await walker(homes, failing, registry).walk(Home.EU)
    unclaimed = await runs(run_slot.claimed.connections[Home.EU])
    healthy = RecordingTicks()
    retried = await walker(homes, healthy).walk(Home.EU)

    assert failed == WalkResult(queued=[DAILY_EU.name], failed=[HOURLY.name])
    assert unclaimed == {HOURLY.name: False, DAILY_EU.name: True}
    assert retried == WalkResult(queued=[HOURLY.name])
    labels = {"job": HOURLY.name, "home": "eu", "outcome": "failed"}
    assert registry.get_sample_value("shosai_periodic_job_runs_total", labels) == 1


async def test_a_job_still_in_flight_keeps_its_claim_for_this_interval(
    homes: DatabaseAccess,
) -> None:
    busy = RecordingTicks(in_flight={HOURLY.name})

    skipped = await walker(homes, busy).walk(Home.RU)
    later = await walker(homes, RecordingTicks()).walk(Home.RU)

    assert skipped == WalkResult(skipped=[HOURLY.name])
    assert later == WalkResult()


async def test_a_job_unknown_to_the_code_is_left_alone(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.RU]
    await connection.execute(
        "INSERT INTO schedule_runs (job_name, last_run_at) VALUES ('retired.job', '2026-01-01+00')"
    )

    await walker(homes, RecordingTicks()).walk(Home.RU)

    rows = await fetch_rows(
        connection, "SELECT last_run_at::date::text AS day FROM schedule_runs "
        "WHERE job_name = 'retired.job'"
    )  # fmt: skip
    assert [row["day"] for row in rows] == ["2026-01-01"]


def test_a_job_declared_twice_is_refused(homes: DatabaseAccess) -> None:
    with pytest.raises(ValueError, match=HOURLY.name):
        ScheduleWalker(
            homes.transactions, RecordingTicks(), ScheduleMetrics(CollectorRegistry()),
            (HOURLY, HOURLY),
        )  # fmt: skip


async def test_the_interval_is_measured_by_the_database_clock(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    ticks = RecordingTicks()
    await walker(homes, ticks).walk(Home.RU)
    connection = run_slot.claimed.connections[Home.RU]
    await connection.execute("UPDATE schedule_runs SET last_run_at = now() - interval '59 minutes'")

    early = await walker(homes, ticks).walk(Home.RU)

    assert early == WalkResult()
    assert HOURLY.every == timedelta(hours=1)
