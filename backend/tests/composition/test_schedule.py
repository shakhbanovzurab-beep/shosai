"""Core's daily jobs are periodic jobs; a scheduled task the process lacks stops the start."""

from datetime import timedelta

import pytest
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.composition.schedule import CORE_JOBS, scheduled_jobs
from shosai.core.features import FeatureParts
from shosai.core.schedule.jobs import DueRowSource, PeriodicJob
from shosai.core.tasks.declaration import TaskHandler
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.system import TaskSystem, build_task_system
from tests.core.schedule.jobs_bench import tick

DIGEST = tick("probe.hourly_digest")
SWEEP = tick("probe.sweep_due")


async def nothing(_payload: HomeTaskPayload) -> None:
    """A tick that does nothing."""


def task_system(valkey: Redis, *registered: str) -> TaskSystem:
    """A task system with core's jobs and the named probe ticks registered."""
    tasks = build_task_system(valkey, CollectorRegistry(), TracerProvider())
    probes = {task.name: task for task in (DIGEST, SWEEP)}
    tasks.register(
        [
            *(TaskHandler(job.task, nothing) for job in CORE_JOBS),
            *(TaskHandler(probes[name], nothing) for name in registered),
        ]
    )
    return tasks


def test_core_runs_its_purges_upkeep_rate_fetch_and_price_sync_as_periodic_jobs() -> None:
    assert {job.name: job.every for job in CORE_JOBS} == {
        "events.purge_outbox": timedelta(days=1),
        "idempotency.purge_keys": timedelta(days=1),
        "db.maintain_partitions": timedelta(days=1),
        "exchange_rates.fetch": timedelta(hours=6),
        "ai.sync_prices": timedelta(days=1),
        "email.purge": timedelta(days=1),
        "ai.reconcile_costs": timedelta(hours=1),
    }


def test_a_slice_job_joins_core_s_jobs(valkey: Redis) -> None:
    parts = FeatureParts(periodic_jobs=(PeriodicJob(DIGEST, timedelta(hours=1)),))

    jobs = scheduled_jobs(parts, task_system(valkey, DIGEST.name))

    assert [job.name for job in jobs][-1] == DIGEST.name


@pytest.mark.parametrize(
    "parts",
    [
        FeatureParts(periodic_jobs=(PeriodicJob(DIGEST, timedelta(hours=1)),)),
        FeatureParts(due_sources=(DueRowSource(SWEEP, timedelta(seconds=5)),)),
    ],
)
def test_a_scheduled_task_this_process_did_not_register_stops_the_start(
    valkey: Redis, parts: FeatureParts
) -> None:
    with pytest.raises(ValueError, match="не зарегистрированы"):
        scheduled_jobs(parts, task_system(valkey))


def test_a_job_or_a_source_declared_twice_stops_the_start(valkey: Redis) -> None:
    tasks = task_system(valkey, DIGEST.name, SWEEP.name)
    job = PeriodicJob(DIGEST, timedelta(hours=1))
    source = DueRowSource(SWEEP, timedelta(seconds=5))

    with pytest.raises(ValueError, match="дважды"):
        scheduled_jobs(FeatureParts(periodic_jobs=(job, job)), tasks)
    with pytest.raises(ValueError, match="дважды"):
        scheduled_jobs(FeatureParts(due_sources=(source, source)), tasks)
