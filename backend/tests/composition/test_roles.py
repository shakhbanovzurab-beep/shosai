"""Each role takes the parts it serves from the platform: routes, a queue, the loops."""

import asyncio
import json
import time
from collections import Counter
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis
from taskiq import TaskiqMessage
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import InvalidStatus
from websockets.typing import Origin

from shosai.composition.roles import api_role, scheduler_role, workers_role, ws_role
from shosai.composition.telemetry import ProcessTelemetry
from shosai.core.config.roles import ProcessRole
from shosai.core.config.values import normalize_origin
from shosai.core.features import CoreServices, FeatureModule, FeatureParts, QueueCompanion
from shosai.core.tasks.queues import TaskQueue
from tests.composition.fixture_features import (
    DIGEST_ROUTE,
    DIGEST_SOCKET,
    NOTES_ROUTE,
    TIDY_NOTES,
    Lifecycle,
    TidyNotes,
    digest_feature,
    notes_feature,
)
from tests.composition.platform_bench import PlatformBench, platform_over_slot
from tests.core.tasks.workbench import stream_entries_of
from tests.harness.process_environ import LOOPBACK, loopback_socket
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

# Один тик на дом у relay и у развёртки почты: повторные отметки тика не ставят.
EXPECTED_TICKS = Counter({"events.relay_outbox": 2, "email.sweep": 2})
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


async def critical_ticks(valkey: Redis, until: Counter[str]) -> Counter[str]:
    """The ticks queued on `critical` by task name, once they reach `until` or time runs out."""
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        queued = await stream_entries_of(valkey, "shosai:tasks:critical")
        ticks = Counter(
            TaskiqMessage.model_validate_json(fields[b"data"]).task_name for _, fields in queued
        )
        if ticks >= until or time.monotonic() > deadline:
            return ticks
        await asyncio.sleep(0.05)


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


async def heard_on_stop(client: ClientConnection) -> dict[str, str]:
    """The frame the gateway sends when it stops; the client leaves on it."""
    frame = json.loads(await client.recv())
    await client.close()
    return dict(frame)


async def test_only_the_gateway_takes_sockets_and_it_says_when_it_stops(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    features = (notes_feature(Lifecycle()), digest_feature(Lifecycle()))

    async with platform_over_slot(run_slot, harness_settings, features) as bench:
        origin = Origin(normalize_origin(str(bench.settings.email.public_base_url)))
        url = loopback_socket(bench.settings.server.http_port, DIGEST_SOCKET)
        async with api_role(bench.platform, bench.telemetry):
            with pytest.raises(InvalidStatus):
                await connect(url, origin=origin)
        gateway = ProcessTelemetry(CollectorRegistry(), TracerProvider(shutdown_on_exit=False))
        async with ws_role(bench.platform, gateway):
            client = await connect(url, origin=origin)
            await client.send(json.dumps({"type": "hello", "v": 1, "token": "fixture"}))
            ready = json.loads(await client.recv())
            stop = asyncio.create_task(heard_on_stop(client))
        notice = await stop

    assert ready == {"type": "ready"}
    assert notice == {"type": "server.shutdown"}


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


def companion_feature(lifecycle: Lifecycle) -> FeatureModule:
    """A slice with work beside the default queue's worker and the bulk queue's."""

    def companion(queue: TaskQueue) -> QueueCompanion:
        @asynccontextmanager
        async def run() -> AsyncIterator[None]:
            lifecycle.events.append(f"companion:open:{queue.value}")
            try:
                yield
            finally:
                lifecycle.events.append(f"companion:close:{queue.value}")

        return QueueCompanion(queue, run)

    @asynccontextmanager
    async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
        del services
        yield FeatureParts(
            queue_companions=(companion(TaskQueue.DEFAULT), companion(TaskQueue.BULK))
        )

    return FeatureModule(name="companions", build=build)


async def test_a_worker_runs_its_queue_s_companions_while_it_takes_tasks(
    run_slot: RunSlot, harness_settings: HarnessSettings
) -> None:
    lifecycle = Lifecycle()
    features = (companion_feature(lifecycle),)

    async with (
        platform_over_slot(run_slot, harness_settings, features, ProcessRole.WORKERS) as bench,
        workers_role(TaskQueue.DEFAULT)(bench.platform, bench.telemetry),
    ):
        running = list(lifecycle.events)

    assert running == ["companion:open:default"]
    assert lifecycle.events == ["companion:open:default", "companion:close:default"]


async def test_the_scheduler_runs_the_core_loops_and_the_slices_loops(
    run_slot: RunSlot, harness_settings: HarnessSettings, valkey: Redis
) -> None:
    lifecycle = Lifecycle()
    core = ("events.relay_outbox.ru", "events.relay_outbox.eu", "tasks.queue_monitor")

    async with (
        platform_over_slot(
            run_slot, harness_settings, (notes_feature(lifecycle),), ProcessRole.SCHEDULER
        ) as bench,
        scheduler_role(bench.platform, bench.telemetry) as tasks,
    ):
        await eventually(
            lambda: all(bench.sample(LOOP_SUCCESS, shosai_loop_name=loop) for loop in core)
        )
        await eventually(lambda: "notes:sweep" in lifecycle.events)
        # Под нагрузкой маркер такта может не уложиться в 50 мс: такт ставит следующая
        # итерация, поэтому ждём сами такты, а не успех итераций.
        ticks = await critical_ticks(valkey, until=EXPECTED_TICKS)

    assert {task.get_name() for task in tasks} >= {
        "loop:notes.sweep",
        "loop:events.outbox_monitor",
        "loop:schedule.walk.ru",
        "loop:schedule.walk.eu",
    }
    assert not {task.get_name() for task in tasks} & {"loop:events.purge_outbox.ru"}
    assert all(task.done() for task in tasks)
    assert ticks == EXPECTED_TICKS
