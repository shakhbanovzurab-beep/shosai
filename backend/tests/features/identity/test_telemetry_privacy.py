"""Identity's flows leave no personal data, no secret and no client trace in telemetry (§16.8).

Registration, verification by the mailed code, sign-in, the token on `/v1/auth/me`, a new
name, failed sign-ins, a password reset request and a stranger's path and query run with
canary values through identity's routes, the real logging pipeline at DEBUG, spans of the
app, both homes and Valkey, and the metrics of all of them. No canary may appear anywhere.
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from dataclasses import dataclass
from uuid import uuid4

import httpx
import pytest_asyncio
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.config.values import LogLevel
from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import connect_redis
from shosai.core.observability.span_privacy import PrivateAttributesSampler
from shosai.core.web.app import HttpTelemetry
from tests.core.observability.capture import captured_logs
from tests.core.observability.telemetry_canaries import leaks
from tests.features.identity.registration_bench import (
    BenchOptions,
    RegistrationBench,
    form,
    mailed_codes,
    register,
    registration_bench,
)
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.migrations import clear_homes
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

CLIENT_ADDRESS = "203.0.113.77"


@dataclass(frozen=True, slots=True)
class Traced:
    """The run's homes, Valkey and cache, all reporting their spans into one exporter."""

    homes: DatabaseAccess
    valkey: Redis
    cache: Redis
    provider: TracerProvider
    spans: InMemorySpanExporter


@pytest_asyncio.fixture
async def traced(
    run_slot: RunSlot, harness_settings: HarnessSettings, valkey: Redis, redis_cache: Redis
) -> AsyncIterator[Traced]:
    """Traced clients over the run's slot; the slot's data is cleared after the test."""
    spans = InMemorySpanExporter()
    provider = TracerProvider(sampler=PrivateAttributesSampler(), shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(spans))
    slot = run_slot.claimed.number
    services = harness_settings.services
    try:
        async with AsyncExitStack() as stack:
            homes = await stack.enter_async_context(
                open_database_access(slot_urls(run_slot), ProcessShape(tracer_provider=provider))
            )
            await homes.gate.verify_at_start()
            traced_valkey = connect_redis(services.valkey.for_slot(slot), "tests-privacy", provider)
            stack.push_async_callback(traced_valkey.aclose)
            traced_cache = connect_redis(services.cache.for_slot(slot), "tests-privacy", provider)
            stack.push_async_callback(traced_cache.aclose)
            yield Traced(homes, traced_valkey, traced_cache, provider, spans)
    finally:
        await clear_homes(run_slot.claimed)
        provider.shutdown()


def canary_values() -> dict[str, str]:
    """Values no code would write by chance; each run gets its own."""
    mark = uuid4().hex[:12]
    return {
        "email": f"canary.{mark}@example.test",
        "full_name": f"Zebulon Canary{mark}",
        "new_name": f"Ottilie Canary{mark}",
        "password": f"canary-password-{mark}",
        "wrong_password": f"canary-wrong-{mark}",
        "stranger_email": f"stranger.{mark}@example.test",
        "query_token": f"canary-query-{mark}",
        "user_agent": f"CanaryAgent/{mark}",
        "client_address": CLIENT_ADDRESS,
    }


async def drive_identity(
    bench: RegistrationBench, run_slot: RunSlot, canaries: dict[str, str]
) -> dict[str, str]:
    """Run identity's flows with the canaries; return the secrets the flows handed out."""
    http = bench.http
    http.headers["User-Agent"] = canaries["user_agent"]
    body = form(canaries["email"], password=canaries["password"])
    body["full_name"] = canaries["full_name"]
    registration_id = await register(http, body)
    [code] = await mailed_codes(run_slot, bench.key_ring, Home.RU)
    verified = await http.post(
        "/v1/auth/register/verify", json={"registration_id": str(registration_id), "code": code}
    )
    assert verified.status_code == 201, verified.text
    login = await http.post(
        "/v1/auth/login", json={"email": canaries["email"], "password": canaries["password"]}
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    bearer = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await http.get("/v1/auth/me", headers=bearer)).status_code == 200
    renamed = await http.patch("/v1/me", headers=bearer, json={"full_name": canaries["new_name"]})
    assert renamed.status_code == 200, renamed.text
    await failed_requests(http, canaries)
    secrets = {"code": code, "access_token": tokens["access_token"]}
    secrets["csrf_token"] = tokens["csrf_token"]
    secrets.update({f"cookie {name}": value for name, value in login.cookies.items()})
    return secrets


async def failed_requests(http: httpx.AsyncClient, canaries: dict[str, str]) -> None:
    """Wrong passwords, a stranger's address, a reset request and a path nobody serves."""
    wrong = {"email": canaries["email"], "password": canaries["wrong_password"]}
    assert (await http.post("/v1/auth/login", json=wrong)).status_code == 401
    stranger = {"email": canaries["stranger_email"], "password": canaries["wrong_password"]}
    assert (await http.post("/v1/auth/login", json=stranger)).status_code == 401
    forgot = await http.post("/v1/auth/password/forgot", json={"email": canaries["email"]})
    assert forgot.status_code == 202, forgot.text
    unknown = f"/v1/people/{canaries['stranger_email']}?token={canaries['query_token']}"
    assert (await http.get(unknown)).status_code == 404


async def test_identity_flows_leave_no_personal_data_in_telemetry(
    traced: Traced, run_slot: RunSlot
) -> None:
    canaries = canary_values()
    registry = CollectorRegistry()
    options = BenchOptions(
        telemetry=HttpTelemetry(registry, traced.provider), client=(CLIENT_ADDRESS, 4711)
    )
    with captured_logs(LogLevel.DEBUG) as logs:
        async with registration_bench(
            traced.homes.transactions, traced.valkey, traced.cache, options
        ) as bench:
            secrets = await drive_identity(bench, run_slot, canaries)

    spans = traced.spans.get_finished_spans()
    # Пустая телеметрия прошла бы проверку даром: строки, спаны и метрики должны быть.
    assert logs.lines()
    assert {span.name for span in spans} >= {"POST /v1/auth/login", "SELECT", "EVALSHA"}
    registries = [registry, traced.homes.registry, logs.registry]
    assert leaks({**canaries, **secrets}, logs.text(), spans, registries) == {}
