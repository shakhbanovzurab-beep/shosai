"""Each role takes the parts it serves from the platform: routes, a queue, the loops."""

import asyncio
import time
from collections.abc import Callable

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.composition.roles import api_role, scheduler_role, workers_role, ws_role
from shosai.composition.telemetry import ProcessTelemetry
from shosai.core.config.roles import ProcessRole
from shosai.core.tasks.queues import TaskQueue
from tests.composition.fixture_features import (
    DIGEST_ROUTE,
    NOTES_ROUTE,
    TIDY_NOTES,
    Lifecycle,
    TidyNotes,
    digest_feature,
    notes_feature,
)
from tests.composition.platform_bench import PlatformBench, platform_over_slot
from tests.harness.process_environ import LOOPBACK
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

WAIT_SECONDS = 10.0
LOOP_SUCCESS = "shosai_loop_last_success_timestamp_seconds"


async def get(bench: PlatformBench, path: str) -> httpx.Response:
    """A GET to the public port of the bench's settings."""
    async with httpx.AsyncClient(timeout=5) as client:
        return await client.get(f"http://{LOOPBACK}:{bench.settings.server.http_port}{path}")


async def eventually(holds: Callable[[], bool]) -> None:
    """Wait until `holds` is true; fail the test when it is not within the bound."""
    deadline = time.monotonic() + WAIT_SECONDS
    while not holds():
        if time.monotonic() > deadline:
            pytest.fail(f"условие не выполнилось за {WAIT_SECONDS} с", pytrace=False)
        await asyncio.sleep(0.02)


async def test_the_api_and_the_gateway_each_serve_their_own_routes(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    features = (notes_feature(Lifecycle()), digest_feature(Lifecycle()))

    async with platform_over_slot(run_slot, harness_settings, features) as bench:
        async with api_role(bench.platform, bench.telemetry):
            notes, digest_on_api = await get(bench, NOTES_ROUTE), await get(bench, DIGEST_ROUTE)
        # Шлюз WS — другой процесс со своим реестром метрик.
        gateway = ProcessTelemetry(CollectorRegistry(), TracerProvider(shutdown_on_exit=False))
        async with ws_role(bench.platform, gateway):
            digest, notes_on_ws = await get(bench, DIGEST_ROUTE), await get(bench, NOTES_ROUTE)

    assert (notes.status_code, notes.json()) == (200, {"role": "api"})
    assert (digest.status_code, digest.json()) == (200, {"status": "ok"})
    assert digest_on_api.status_code == notes_on_ws.status_code == 404


async def test_a_worker_runs_the_tasks_of_its_queue(
    run_slot: RunSlot, harness_settings: HarnessSettings, valkey: Redis
) -> None:
    lifecycle = Lifecycle()
    features = (notes_feature(lifecycle),)

    async with (
        platform_over_slot(run_slot, harness_settings, features, ProcessRole.WORKERS) as bench,
        workers_role(TaskQueue.DEFAULT)(bench.platform, bench.telemetry),
    ):
        await bench.platform.tasks.sender.send(TIDY_NOTES, TidyNotes())
        await eventually(lambda: "notes:tidy" in lifecycle.events)

    assert lifecycle.events.count("notes:tidy") == 1


async def test_the_scheduler_runs_the_core_loops_and_the_slices_loops(
    run_slot: RunSlot, harness_settings: HarnessSettings, valkey: Redis
) -> None:
    lifecycle = Lifecycle()
    core = ("events.relay_outbox.ru", "events.relay_outbox.eu", "tasks.queue_monitor")

    async with platform_over_slot(
        run_slot, harness_settings, (notes_feature(lifecycle),), ProcessRole.SCHEDULER
    ) as bench:
        async with scheduler_role(bench.platform, bench.telemetry) as tasks:
            await eventually(
                lambda: all(bench.sample(LOOP_SUCCESS, shosai_loop_name=loop) for loop in core)
            )
            await eventually(lambda: "notes:sweep" in lifecycle.events)
        relay_ticks = int(await valkey.xlen("shosai:tasks:critical"))

    assert {task.get_name() for task in tasks} >= {
        "loop:notes.sweep",
        "loop:events.outbox_monitor",
        "loop:schedule.walk.ru",
        "loop:schedule.walk.eu",
    }
    assert not {task.get_name() for task in tasks} & {"loop:events.purge_outbox.ru"}
    assert all(task.done() for task in tasks)
    assert relay_ticks == 2
