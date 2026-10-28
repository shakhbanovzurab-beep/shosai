"""The grant lifecycle: one refresh at a time, rotated tokens kept, refusals told apart, a
revocation on the last app only, retried and finally forgotten, keep-alive from due rows
(connectors plan §3.5)."""

import asyncio
import uuid
from datetime import timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select, update

from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.contracts import NeedsReconnectError
from shosai.features.connectors.contracts.provider import ProviderUnavailableError
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.metrics import CLIENT_MISCONFIGURED, REVOKE_FAILURES
from shosai.features.connectors.infrastructure.store.records import (
    ConnectionRecord,
    GrantRecord,
    GrantSecretRecord,
)
from tests.features.connectors.connect_bench import connect_bench
from tests.features.connectors.lifecycle_bench import LifecycleBench, Person, lifecycle

__all__ = ["connect_bench", "lifecycle"]


def someone() -> Person:
    """A new person of the Russian home."""
    return Home.RU, uuid.uuid4()


async def grant_row(bench: LifecycleBench, person: Person, grant_id: uuid.UUID) -> GrantRecord:
    """The grant as stored now."""
    home, user_id = person
    async with bench.connect.homes.transactions.begin(TenancyScope(home, user_id)) as session:
        return (
            await session.execute(select(GrantRecord).where(GrantRecord.id == grant_id))
        ).scalar_one()


async def broken_events(bench: LifecycleBench) -> int:
    """How many broken events the home's outbox holds."""
    async with bench.connect.homes.transactions.begin(TenancyScope(Home.RU), read_only=True) as s:
        found = await s.scalar(
            select(func.count()).where(OutboxMessage.event_type == "connectors.connection.broken")
        )
    return int(found or 0)


async def test_twenty_callers_make_one_refresh_and_keep_the_rotated_token(
    lifecycle: LifecycleBench,
) -> None:
    person = someone()
    scope = TenancyScope(*person)
    grant_id = await lifecycle.connected(person, App.GOOGLE_CALENDAR)
    await lifecycle.expire(person, grant_id)

    tokens = await asyncio.gather(*(lifecycle.tokens.access(scope, grant_id) for _ in range(20)))

    assert {token.get_secret_value() for token in tokens} == {"access-r1"}
    assert lifecycle.connect.provider.refreshes == 1
    async with lifecycle.connect.homes.transactions.begin(scope) as session:
        secret = (await session.execute(select(GrantSecretRecord))).scalar_one()
    assert secret.refresh_token_enc is not None
    assert lifecycle.connect.keys.decrypt(secret.refresh_token_enc) == "refresh-r1"
    assert secret.refresh_generation == 1
    assert secret.refreshing_until is None
    fresh = await lifecycle.tokens.access(scope, grant_id)
    assert fresh.get_secret_value() == "access-r1"
    again = await lifecycle.tokens.access(scope, grant_id, refused=SecretStr("access-r1"))
    assert again.get_secret_value() == "access-r2"


async def test_a_refused_grant_breaks_every_app_once(lifecycle: LifecycleBench) -> None:
    person = someone()
    scope = TenancyScope(*person)
    grant_id = await lifecycle.connected(person, App.GOOGLE_CALENDAR)
    await lifecycle.connected(person, App.GOOGLE_DRIVE)
    await lifecycle.expire(person, grant_id)
    lifecycle.connect.provider.refresh_mode = "refused"

    with pytest.raises(NeedsReconnectError) as refused:
        await lifecycle.tokens.access(scope, grant_id)
    with pytest.raises(NeedsReconnectError):
        await lifecycle.tokens.access(scope, grant_id)

    assert refused.value.problem.value == "refresh_refused"
    grant = await grant_row(lifecycle, person, grant_id)
    assert (grant.status, grant.problem) == ("needs_reconnect", "refresh_refused")
    assert await broken_events(lifecycle) == 2


async def test_a_refusal_of_shosai_s_application_breaks_nothing(lifecycle: LifecycleBench) -> None:
    person = someone()
    grant_id = await lifecycle.connected(person, App.GOOGLE_CALENDAR)
    await lifecycle.expire(person, grant_id)
    lifecycle.connect.provider.refresh_mode = "client"

    with pytest.raises(ProviderUnavailableError):
        await lifecycle.tokens.access(TenancyScope(*person), grant_id)

    grant = await grant_row(lifecycle, person, grant_id)
    assert (grant.status, grant.consecutive_failures) == ("active", 1)
    sample = lifecycle.metrics.get_sample_value(CLIENT_MISCONFIGURED, {"client": "google"})
    assert sample == 1
    assert await broken_events(lifecycle) == 0


async def test_only_the_last_app_s_disconnect_revokes(lifecycle: LifecycleBench) -> None:
    person = someone()
    scope = TenancyScope(*person)
    grant_id = await lifecycle.connected(person, App.GOOGLE_CALENDAR)
    await lifecycle.connected(person, App.GOOGLE_DRIVE)

    first = await lifecycle.disconnector.disconnect(scope, App.GOOGLE_DRIVE)
    assert first.access_remains_at_provider
    assert (await grant_row(lifecycle, person, grant_id)).status == "active"
    last = await lifecycle.disconnector.disconnect(scope, App.GOOGLE_CALENDAR)
    assert not last.access_remains_at_provider
    assert (await grant_row(lifecycle, person, grant_id)).status == "revoking"

    async with lifecycle.workers() as workers:
        due = await lifecycle.due(workers).revocations(Home.RU)
    assert [grant.grant_id for grant in due] == [grant_id]
    await lifecycle.revoker.revoke_due(scope, grant_id)
    await lifecycle.revoker.revoke_due(scope, grant_id)

    assert lifecycle.connect.provider.revoked == ["refresh-anna"]
    async with lifecycle.connect.homes.transactions.begin(scope) as session:
        left = await session.scalar(select(func.count()).select_from(GrantSecretRecord))
    assert left == 0


async def test_a_refused_revocation_waits_and_is_forgotten_after_five(
    lifecycle: LifecycleBench,
) -> None:
    person = someone()
    scope = TenancyScope(*person)
    grant_id = await lifecycle.connected(person, App.GOOGLE_CALENDAR)
    await lifecycle.disconnector.disconnect(scope, App.GOOGLE_CALENDAR)
    lifecycle.connect.provider.revoke_failures = 10

    for attempt in range(1, 6):
        await lifecycle.revoker.revoke_due(scope, grant_id)
        if attempt < 5:
            grant = await grant_row(lifecycle, person, grant_id)
            assert grant.consecutive_failures == attempt
            async with lifecycle.connect.homes.transactions.begin(scope) as session:
                await session.execute(
                    update(GrantRecord)
                    .where(GrantRecord.id == grant_id)
                    .values(revoke_at=func.now())
                )

    async with lifecycle.connect.homes.transactions.begin(scope) as session:
        assert await session.scalar(select(func.count()).select_from(GrantRecord)) == 0
    sample = lifecycle.metrics.get_sample_value(REVOKE_FAILURES, {"provider": "google"})
    assert sample == 1


async def test_a_keep_alive_refreshes_an_idle_grant_from_its_due_row(
    lifecycle: LifecycleBench,
) -> None:
    person = someone()
    scope = TenancyScope(*person)
    grant_id = await lifecycle.connected(person, App.GOOGLE_CALENDAR)
    async with lifecycle.connect.homes.transactions.begin(scope) as session:
        await session.execute(
            update(GrantSecretRecord).values(keepalive_at=func.now() - timedelta(minutes=1))
        )

    async with lifecycle.workers() as workers:
        due = await lifecycle.due(workers).keepalive(Home.RU)
    await lifecycle.tokens.keep_alive(scope, grant_id)
    await lifecycle.tokens.keep_alive(scope, grant_id)

    assert [grant.grant_id for grant in due] == [grant_id]
    assert lifecycle.connect.provider.refreshes == 1
    async with lifecycle.connect.homes.transactions.begin(scope) as session:
        connections = await session.scalar(select(func.count()).select_from(ConnectionRecord))
    assert connections == 1
