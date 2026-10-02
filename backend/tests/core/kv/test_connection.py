"""Redis-protocol clients: named, bounded, never retrying, traced without values."""

import asyncio
from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from tests.core.db.tcp_proxy import LOOPBACK
from tests.core.kv.outages import redis_url, through, upstream_of
from whisperer.core.kv.connection import MAX_CONNECTIONS, connect_redis
from whisperer.core.kv.keys import build_key
from whisperer.core.observability.span_privacy import PrivateAttributesSampler

SECRET_VALUE = "a-value-that-must-not-reach-a-span"


@pytest.fixture
def spans() -> Iterator[tuple[TracerProvider, InMemorySpanExporter]]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=PrivateAttributesSampler(), shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield provider, exporter
    provider.shutdown()


async def test_commands_are_client_spans_without_values(
    valkey: Redis, spans: tuple[TracerProvider, InMemorySpanExporter]
) -> None:
    provider, exporter = spans
    client = connect_redis(through(valkey, upstream_of(valkey).port), "whisperer-tests", provider)

    await client.set(build_key("probe", "span"), SECRET_VALUE)
    await client.aclose()

    [span] = [span for span in exporter.get_finished_spans() if span.name == "SET"]
    assert span.kind is SpanKind.CLIENT
    attributes = {key: str(value) for key, value in (span.attributes or {}).items()}
    assert "SET ? ?" in attributes.values()
    assert not any(SECRET_VALUE in value or "probe" in value for value in attributes.values())


async def test_the_client_names_its_process_and_bounds_its_pool(valkey: Redis) -> None:
    client = connect_redis(through(valkey, upstream_of(valkey).port), "whisperer-api")

    name = await client.client_getname()

    assert name in {"whisperer-api", b"whisperer-api"}
    assert client.connection_pool.max_connections == MAX_CONNECTIONS
    await client.aclose()


async def test_a_failed_connection_is_not_retried_by_the_client() -> None:
    attempts = 0

    async def refuse(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal attempts
        attempts += 1
        writer.close()

    server = await asyncio.start_server(refuse, LOOPBACK, 0)
    client = connect_redis(redis_url(int(server.sockets[0].getsockname()[1])), "whisperer-tests")

    with pytest.raises(RedisConnectionError):
        await client.ping()

    assert attempts == 1
    await client.aclose()
    server.close()
    await server.wait_closed()
