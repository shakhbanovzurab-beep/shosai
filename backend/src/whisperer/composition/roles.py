"""What each role runs on the platform: a public server, a queue's worker or the loops (§5).

A role is an async context manager: entering it starts the role's work and gives the
tasks that run it; leaving it drains that work. The process watches the tasks — one that
ends by itself is a failure — and leaves the role when asked to stop.

| Role | Runs |
|---|---|
| `api` | the public app: the slices' HTTP routers and `GET /v1/health` |
| `ws` | the public app of the WS gateway: the slices' WebSocket routers and `GET /v1/health` |
| `workers --queue Q` | TaskIQ's receiver of one queue |
| `scheduler` | the loops: outbox relay and purge, queue and outbox gauges, the slices' loops |
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import timedelta
from typing import Final

from fastapi import APIRouter, FastAPI

from whisperer.composition.platform import Platform
from whisperer.composition.scheduler import core_loops
from whisperer.composition.telemetry import ProcessTelemetry
from whisperer.core.runtime.loops import LoopMetrics, LoopRunner
from whisperer.core.runtime.servers import EDGE_KEEP_ALIVE, HttpServer, server_config
from whisperer.core.tasks.queues import TaskQueue
from whisperer.core.tasks.worker import consume_queue
from whisperer.core.web.app import HttpTelemetry, build_http_app, forwarded_allow_ips

# Ожидание начатых запросов при остановке: как у воркеров (core/tasks/worker.py); вместе с
# закрытием клиентов укладывается в отсрочку остановки контейнера (composition/process.py).
PUBLIC_DRAIN: Final = timedelta(seconds=20)

type RoleTasks = tuple[asyncio.Task[None], ...]
type Role = Callable[[Platform, ProcessTelemetry], AbstractAsyncContextManager[RoleTasks]]


def public_app(
    platform: Platform, telemetry: ProcessTelemetry, routers: Sequence[APIRouter]
) -> FastAPI:
    """The public app of `api` or `ws` with the given slices' routers and the health route."""
    return build_http_app(
        platform.services.settings.web,
        HttpTelemetry(telemetry.registry, telemetry.tracer_provider),
        routers,
    )


@asynccontextmanager
async def serve_public_app(
    platform: Platform, telemetry: ProcessTelemetry, name: str, routers: Sequence[APIRouter]
) -> AsyncIterator[RoleTasks]:
    """The public app on `HTTP_PORT`, trusting `X-Forwarded-*` from the edge only."""
    settings = platform.services.settings
    config = server_config(
        public_app(platform, telemetry, routers),
        trusted_proxies=forwarded_allow_ips(settings.web),
        drain=PUBLIC_DRAIN,
        keep_alive=EDGE_KEEP_ALIVE,
    )
    server = HttpServer(name, config, str(settings.server.bind_host), settings.server.http_port)
    await server.start()
    try:
        yield (server.task,)
    finally:
        await server.stop()


def api_role(
    platform: Platform, telemetry: ProcessTelemetry
) -> AbstractAsyncContextManager[RoleTasks]:
    """The API: every slice's HTTP routes."""
    return serve_public_app(platform, telemetry, "api", platform.parts.http_routers)


def ws_role(
    platform: Platform, telemetry: ProcessTelemetry
) -> AbstractAsyncContextManager[RoleTasks]:
    """The WS gateway: every slice's WebSocket routes."""
    return serve_public_app(platform, telemetry, "ws", platform.parts.ws_routers)


def workers_role(queue: TaskQueue) -> Role:
    """A worker of one queue: one message at a time per run slot, drained on stop."""

    @asynccontextmanager
    async def consume(platform: Platform, _telemetry: ProcessTelemetry) -> AsyncIterator[RoleTasks]:
        stop = asyncio.Event()
        broker = platform.tasks.brokers[queue]
        worker = asyncio.create_task(consume_queue(broker, stop), name=f"worker:{queue.value}")
        try:
            yield (worker,)
        finally:
            stop.set()
            await worker

    return consume


@asynccontextmanager
async def scheduler_role(
    platform: Platform, telemetry: ProcessTelemetry
) -> AsyncIterator[RoleTasks]:
    """The scheduler: core loops and every slice's loops, each in its own task."""
    runner = LoopRunner(
        [*core_loops(platform), *platform.parts.loops], LoopMetrics(telemetry.registry)
    )
    tasks = runner.start()
    try:
        yield tasks
    finally:
        await runner.stop()
