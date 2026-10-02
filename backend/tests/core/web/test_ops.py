"""The ops app: liveness, readiness by phase, metrics in the format the scraper asks for."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from prometheus_client import CollectorRegistry, Counter

from whisperer.core.health.probes import DependencyProbe
from whisperer.core.health.readiness import Readiness
from whisperer.core.web.ops import build_ops_app

OPENMETRICS = "application/openmetrics-text"


async def answers() -> None:
    """A dependency that answers."""


@asynccontextmanager
async def ops_client(
    readiness: Readiness, registry: CollectorRegistry
) -> AsyncIterator[httpx.AsyncClient]:
    """A client of the ops app over ASGI."""
    transport = httpx.ASGITransport(app=build_ops_app(readiness, registry))
    async with httpx.AsyncClient(transport=transport, base_url="http://ops") as client:
        yield client


async def test_liveness_answers_in_every_phase() -> None:
    readiness = Readiness()

    async with ops_client(readiness, CollectorRegistry()) as client:
        starting = await client.get("/livez")
        readiness.ready(())
        readiness.drain()
        draining = await client.get("/livez")

    assert starting.json() == draining.json() == {"status": "ok"}
    assert starting.status_code == draining.status_code == 200


async def test_readiness_follows_the_phase_of_the_process() -> None:
    readiness = Readiness()

    async with ops_client(readiness, CollectorRegistry()) as client:
        starting = await client.get("/readyz")
        readiness.ready((DependencyProbe("valkey", answers, ()),))
        ready = await client.get("/readyz")
        readiness.drain()
        draining = await client.get("/readyz")

    assert (starting.status_code, starting.json()["status"]) == (503, "starting")
    assert (ready.status_code, ready.json()) == (
        200,
        {"status": "ready", "dependencies": {"valkey": "ok"}},
    )
    assert (draining.status_code, draining.json()["status"]) == (503, "draining")


async def test_metrics_come_from_the_process_registry_in_the_asked_format() -> None:
    registry = CollectorRegistry()
    Counter("whisperer_probe_events", "Пробные события", registry=registry).inc()

    async with ops_client(Readiness(), registry) as client:
        text = await client.get("/metrics")
        openmetrics = await client.get("/metrics", headers={"Accept": OPENMETRICS})

    assert text.headers["content-type"].startswith("text/plain")
    assert "whisperer_probe_events_total 1.0" in text.text
    assert openmetrics.headers["content-type"].startswith(OPENMETRICS)
    assert openmetrics.text.endswith("# EOF\n")


async def test_the_ops_app_publishes_no_docs_or_schema() -> None:
    async with ops_client(Readiness(), CollectorRegistry()) as client:
        statuses = [(await client.get(path)).status_code for path in ("/docs", "/openapi.json")]

    assert statuses == [404, 404]
