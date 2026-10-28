"""Provider sessions over the connect bench, against an API double at `https://api.test`.

The double answers by path: `/data` echoes the Authorization header, `/stale` refuses the
first token and takes a refreshed one, `/gone` refuses every token, `/throttle` answers 429
with `Retry-After: 7`, `/flaky` fails once with 502, `/down` answers 503 without a wait,
`/slow` holds the answer until the test lets it go, `/quota` says 90% of the application's
quota is used.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Final

import httpx
import pytest_asyncio
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry
from pydantic import SecretStr
from redis.asyncio import Redis

from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.features.connectors.application.grant_tokens import GrantTokens, TokenTools
from shosai.features.connectors.application.provider_access import ConnectorProviderAccess
from shosai.features.connectors.domain.descriptors import LimitSubject, ProviderLimit
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.oauth.tokens import ClientCredentials
from shosai.features.connectors.infrastructure.providers.base import (
    ConfiguredClient,
    ProviderRegistry,
)
from shosai.features.connectors.infrastructure.transport.guards import ProviderGuards
from shosai.features.connectors.infrastructure.transport.session import SessionParts
from tests.features.connectors.connect_bench import GOOGLE, ConnectBench, DoubleAdapter
from tests.features.connectors.lifecycle_bench import LifecycleBench

# Ответы, не зависящие ни от токена, ни от числа вызовов.
FIXED: Final[dict[str, tuple[int, dict[str, str]]]] = {
    "/throttle": (429, {"Retry-After": "7"}),
    "/down": (503, {}),
    "/quota": (200, {"RateLimit-Policy": '"app";q=100;w=3600', "RateLimit": '"app";r=10;t=60'}),
}


@dataclass
class ApiDouble:
    """A provider's API answering by path, counting its calls."""

    calls: list[str] = field(default_factory=list)
    released: asyncio.Event = field(default_factory=asyncio.Event)

    async def handle(self, request: httpx.Request) -> httpx.Response:
        """One API call."""
        path, auth = request.url.path, request.headers.get("Authorization", "")
        self.calls.append(f"{request.method} {path}")
        if path == "/data":
            return httpx.Response(200, json={"auth": auth})
        if path in {"/stale", "/gone"} and (path == "/gone" or auth.endswith("access-anna")):
            return httpx.Response(401, json={"error": "invalid_token"})
        if path in FIXED:
            status, headers = FIXED[path]
            return httpx.Response(status, headers=headers)
        if path == "/flaky" and self.calls.count(f"{request.method} {path}") == 1:
            return httpx.Response(502)
        if path == "/slow":
            await self.released.wait()
        return httpx.Response(200, json={"auth": auth, "path": path})


@dataclass(frozen=True, slots=True)
class TransportBench:
    """Sessions with the API double; the descriptor is Google's with test quotas."""

    access: ConnectorProviderAccess
    api: ApiDouble
    lifecycle: LifecycleBench
    spans: InMemorySpanExporter
    counters: CollectorRegistry


LIMITED = replace(
    GOOGLE,
    limits=(ProviderLimit("calls", LimitSubject.ACCOUNT, 8, timedelta(minutes=1), burst=8),),
    concurrency_per_account=1,
)


@pytest_asyncio.fixture
async def transport(lifecycle: LifecycleBench, valkey: Redis) -> AsyncIterator[TransportBench]:
    """Sessions over a registry whose Google application has test quotas."""
    connect: ConnectBench = lifecycle.connect
    api = ApiDouble()

    async def route(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.test":
            return await api.handle(request)
        return connect.provider.handle(request)

    credentials = ClientCredentials("client-id", SecretStr("client-secret"))
    registry = ProviderRegistry(
        {"google": ConfiguredClient(DoubleAdapter(LIMITED, connect.provider), credentials)}
    )
    counters, spans = CollectorRegistry(), InMemorySpanExporter()
    tracing = TracerProvider()
    tracing.add_span_processor(SimpleSpanProcessor(spans))
    metrics = ConnectorsMetrics(counters)
    _registry, _http, outbox = connect.wiring
    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        tokens = GrantTokens(
            connect.homes.transactions, TokenTools(registry, http, connect.keys, outbox, metrics)
        )
        guards = ProviderGuards(valkey, RateLimiter(valkey, KeyValueMetrics(counters)))
        parts = SessionParts(tokens, guards, http, metrics, tracing.get_tracer("test"))
        access = ConnectorProviderAccess(connect.homes.transactions, registry, parts)
        yield TransportBench(access, api, lifecycle, spans, counters)


def body_of(content: bytes) -> dict[str, object]:
    """A JSON answer's object."""
    loaded = json.loads(content)
    assert isinstance(loaded, dict)
    return loaded
