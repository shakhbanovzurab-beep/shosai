"""Provider sessions: the token injected and refreshed once on a 401, the grant gone after a
second, `Retry-After` shared, reads retried and writes never, the breaker counting only the
provider's failures, quotas and concurrency, no token in a span (connectors plan §3.6)."""

import asyncio
import uuid

import pytest
import structlog
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.contracts import (
    NeedsReconnectError,
    NotConnectedError,
    ProviderBusyError,
    ProviderCall,
)
from shosai.features.connectors.contracts.provider import ProviderUnavailableError
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.metrics import CALLS
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord
from tests.features.connectors.connect_bench import connect_bench
from tests.features.connectors.lifecycle_bench import lifecycle
from tests.features.connectors.transport_bench import TransportBench, body_of, transport

__all__ = ["connect_bench", "lifecycle", "transport"]


async def connection_of(bench: TransportBench) -> tuple[TenancyScope, uuid.UUID]:
    """A person with Google Calendar connected, and the connection's id."""
    person = (Home.RU, uuid.uuid4())
    await bench.lifecycle.connected(person, App.GOOGLE_CALENDAR)
    scope = TenancyScope(*person)
    async with bench.lifecycle.connect.homes.transactions.begin(scope) as session:
        connection_id = await session.scalar(select(ConnectionRecord.id))
    assert connection_id is not None
    return scope, connection_id


def get(path: str, method: str = "GET") -> ProviderCall:
    """A call of the test operation."""
    return ProviderCall(method, "calendar.read", f"https://api.test{path}")


async def test_the_token_goes_in_the_header_and_a_401_refreshes_once(
    transport: TransportBench,
) -> None:
    scope, connection_id = await connection_of(transport)
    with structlog.testing.capture_logs() as logs:
        async with transport.access.open(scope, connection_id) as session:
            data = await session.request(get("/data"))
            stale = await session.request(get("/stale"))

    assert body_of(data.body)["auth"] == "Bearer access-anna"
    assert body_of(stale.body)["auth"] == "Bearer access-r1"
    assert transport.lifecycle.connect.provider.refreshes == 1
    assert "access-anna" not in str(logs)
    for span in transport.spans.get_finished_spans():
        assert "access" not in str(dict(span.attributes or {}))
        assert span.attributes is not None
        assert span.attributes["connectors.operation"] == "calendar.read"
    sample = transport.counters.get_sample_value(
        CALLS, {"provider": "google", "operation": "calendar.read", "outcome": "2xx"}
    )
    assert sample == 2


async def test_a_fresh_token_refused_means_the_grant_is_gone(transport: TransportBench) -> None:
    scope, connection_id = await connection_of(transport)

    async with transport.access.open(scope, connection_id) as session:
        with pytest.raises(NeedsReconnectError) as gone:
            await session.request(get("/gone"))
    calls = len(transport.api.calls)
    with pytest.raises(NeedsReconnectError):
        async with transport.access.open(scope, connection_id) as session:
            await session.request(get("/data"))

    assert gone.value.problem.value == "grant_revoked"
    assert len(transport.api.calls) == calls


async def test_a_retry_after_stops_the_account_in_every_session(transport: TransportBench) -> None:
    scope, connection_id = await connection_of(transport)

    async with transport.access.open(scope, connection_id) as session:
        with pytest.raises(ProviderBusyError) as busy:
            await session.request(get("/throttle"))
    async with transport.access.open(scope, connection_id) as other:
        with pytest.raises(ProviderBusyError):
            await other.request(get("/data"))

    assert busy.value.retry_after_seconds == 7
    assert transport.api.calls == ["GET /throttle"]


async def test_a_read_is_tried_again_and_a_write_never(transport: TransportBench) -> None:
    scope, connection_id = await connection_of(transport)

    async with transport.access.open(scope, connection_id) as session:
        read = await session.request(get("/flaky"))
        with pytest.raises(ProviderUnavailableError):
            await session.request(get("/flaky", method="POST"))

    assert read.status == 200
    assert transport.api.calls == ["GET /flaky", "GET /flaky", "POST /flaky"]


async def test_the_breaker_opens_on_the_provider_s_failures_only(transport: TransportBench) -> None:
    scope, connection_id = await connection_of(transport)
    other_scope, other_connection = await connection_of(transport)

    async with transport.access.open(other_scope, other_connection) as revoked:
        with pytest.raises(NeedsReconnectError):
            await revoked.request(get("/gone"))
    async with transport.access.open(scope, connection_id) as session:
        assert (await session.request(get("/data"))).status == 200
        for _ in range(3):
            with pytest.raises(ProviderUnavailableError):
                await session.request(get("/down"))
        calls = len(transport.api.calls)
        with pytest.raises(ProviderUnavailableError):
            await session.request(get("/data"))

    assert len(transport.api.calls) == calls


async def test_quotas_and_concurrency_of_an_account(transport: TransportBench) -> None:
    scope, connection_id = await connection_of(transport)

    async with transport.access.open(scope, connection_id) as session:
        held = asyncio.create_task(session.request(get("/slow")))
        await asyncio.sleep(0.2)
        with pytest.raises(ProviderBusyError):
            await session.request(get("/data"))
        transport.api.released.set()
        assert (await held).status == 200
        for _ in range(6):
            await session.request(get("/data"))
        with pytest.raises(ProviderBusyError):
            await session.request(get("/data"))

    assert transport.api.calls.count("GET /data") == 6


async def test_a_stranger_s_connection_and_a_bad_call_are_refused(
    transport: TransportBench,
) -> None:
    _scope, connection_id = await connection_of(transport)
    stranger = TenancyScope(Home.RU, uuid.uuid4())

    with pytest.raises(NotConnectedError):
        async with transport.access.open(stranger, connection_id):
            pass
    async with transport.access.open(_scope, connection_id) as session:
        with pytest.raises(ValueError, match="HTTPS"):
            await session.request(ProviderCall("GET", "calendar.read", "http://api.test/data"))
        with pytest.raises(ValueError, match="операции"):
            await session.request(ProviderCall("GET", "Read", "https://api.test/data"))
