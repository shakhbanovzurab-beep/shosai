"""Provider sessions over the Google bench, with an API double behind a host of its own."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import httpx
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.features.connectors.application.grant_tokens import GrantTokens, TokenTools
from shosai.features.connectors.application.provider_access import ConnectorProviderAccess
from shosai.features.connectors.infrastructure.metrics import ConnectorsMetrics
from shosai.features.connectors.infrastructure.providers.base import ProviderRegistry
from shosai.features.connectors.infrastructure.transport.guards import ProviderGuards
from shosai.features.connectors.infrastructure.transport.session import SessionParts
from tests.features.connectors.google_bench import GoogleBench

type Handler = Callable[[httpx.Request], httpx.Response]


@asynccontextmanager
async def provider_access(
    google: GoogleBench,
    valkey: Redis,
    api: tuple[str, Handler],
    registry: ProviderRegistry | None = None,
) -> AsyncIterator[ConnectorProviderAccess]:
    """`PROVIDER_ACCESS` whose calls to `api`'s host reach its handler, the rest Google's."""
    host, handler = api
    bench_registry, outbox = google.wiring
    applications = registry or bench_registry

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.host == host:
            return handler(request)
        return google.google.handle(request)

    counters = CollectorRegistry()
    metrics = ConnectorsMetrics(counters)
    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as http:
        tokens = GrantTokens(
            google.homes.transactions, TokenTools(applications, http, google.keys, outbox, metrics)
        )
        guards = ProviderGuards(valkey, RateLimiter(valkey, KeyValueMetrics(counters)))
        parts = SessionParts(tokens, guards, http, metrics, TracerProvider().get_tracer("t"))
        yield ConnectorProviderAccess(google.homes.transactions, applications, parts)
