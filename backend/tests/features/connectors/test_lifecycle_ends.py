"""How grants end beyond a disconnect: a deleted workspace, an erased account, and the weekly
key pass that re-encrypts and counts what no key opens (connectors plan §3.5)."""

import uuid
from datetime import UTC, datetime

from cryptography.fernet import Fernet
from prometheus_client import CollectorRegistry
from pydantic import SecretStr
from sqlalchemy import func, insert, select

from shosai.core.account_data.handlers import AccountRef
from shosai.core.crypto.key_ring import FernetKeyRing
from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.account_data import ConnectorsAccountData
from shosai.features.connectors.application.key_rotation import KeyRotation
from shosai.features.connectors.channels.subscriptions import scope_of_workspace, subscriptions
from shosai.features.connectors.domain.catalogue import App, Provider
from shosai.features.connectors.infrastructure.metrics import UNDECRYPTABLE, ConnectorsMetrics
from shosai.features.connectors.infrastructure.store.records import (
    ConnectionRecord,
    GrantRecord,
    GrantSecretRecord,
)
from shosai.features.workspaces.contracts.events import WorkspaceDeleted
from tests.features.connectors.connect_bench import connect_bench
from tests.features.connectors.lifecycle_bench import LifecycleBench, lifecycle

__all__ = ["connect_bench", "lifecycle"]


async def test_a_deleted_workspace_s_installations_end(lifecycle: LifecycleBench) -> None:
    home, admin, org = Home.RU, uuid.uuid4(), uuid.uuid4()
    lifecycle.connect.workspaces.admins[org] = {admin}
    await lifecycle.connect.finish(
        await lifecycle.connect.start((home, admin), App.SLACK, org), "ok:team-1",
        provider=Provider.SLACK,
    )  # fmt: skip
    _registry, _http, outbox = lifecycle.connect.wiring
    (subscription,) = subscriptions(outbox)
    event = WorkspaceDeleted(org_id=org)
    received = ReceivedEvent(event, uuid.uuid4(), 1, datetime.now(UTC), TenancyScope(home))
    scope = scope_of_workspace(event, TenancyScope(home))

    for _ in range(2):
        async with lifecycle.connect.homes.transactions.begin(scope) as session:
            await subscription.handle(session, received)

    async with lifecycle.connect.homes.transactions.begin(scope, read_only=True) as session:
        assert await session.scalar(select(func.count()).select_from(ConnectionRecord)) == 0
        statuses = (await session.execute(select(GrantRecord.status))).scalars().all()
    assert statuses == ["revoking"]


async def test_an_erased_account_s_grants_are_revoked_first(lifecycle: LifecycleBench) -> None:
    home, person, org = Home.RU, uuid.uuid4(), uuid.uuid4()
    await lifecycle.connected((home, person), App.GOOGLE_CALENDAR)
    lifecycle.connect.workspaces.admins[org] = {person}
    await lifecycle.connect.finish(
        await lifecycle.connect.start((home, person), App.SLACK, org), "ok:team-2",
        provider=Provider.SLACK,
    )  # fmt: skip
    handler = ConnectorsAccountData(lifecycle.connect.homes.transactions, lifecycle.revoker)

    await handler.erase(AccountRef(person, home))

    assert lifecycle.connect.provider.revoked == ["refresh-anna"]
    assert await handler.remains(AccountRef(person, home)) == ()
    workspace = TenancyScope(home, person, org)
    async with lifecycle.connect.homes.transactions.begin(workspace, read_only=True) as session:
        assert await session.scalar(select(func.count()).select_from(ConnectionRecord)) == 1


async def seed_secret(lifecycle: LifecycleBench, person: uuid.UUID, ciphertext: bytes) -> uuid.UUID:
    """A personal grant whose refresh token is the given ciphertext."""
    grant_id = uuid.uuid4()
    scope = TenancyScope(Home.RU, person)
    async with lifecycle.connect.homes.transactions.begin(scope) as session:
        await session.execute(insert(GrantRecord).values(
            id=grant_id, user_id=person, provider="google", client_key="google",
            auth_kind="oauth2", external_account_id=str(grant_id),
        ))  # fmt: skip
        await session.execute(insert(GrantSecretRecord).values(
            grant_id=grant_id, user_id=person, refresh_token_enc=ciphertext,
        ))  # fmt: skip
    return grant_id


async def test_the_key_pass_re_encrypts_and_counts_what_no_key_opens(
    lifecycle: LifecycleBench,
) -> None:
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    person = uuid.uuid4()
    await seed_secret(lifecycle, person, FernetKeyRing(SecretStr(old)).encrypt("refresh-old"))
    await seed_secret(lifecycle, person, b"not-a-fernet-token")
    ring = FernetKeyRing(SecretStr(new), [SecretStr(old)])
    counters = CollectorRegistry()

    async with lifecycle.workers() as workers:
        rotation = KeyRotation(workers, ring, rotating=True, metrics=ConnectorsMetrics(counters))
        await rotation.run(Home.RU)

    only_new = FernetKeyRing(SecretStr(new))
    async with lifecycle.connect.homes.transactions.begin(TenancyScope(Home.RU, person)) as s:
        kept = (await s.execute(select(GrantSecretRecord.refresh_token_enc))).scalars().all()
    opened = [
        only_new.decrypt(value)
        for value in kept
        if value is not None and value != b"not-a-fernet-token"
    ]
    assert opened == ["refresh-old"]
    assert counters.get_sample_value(UNDECRYPTABLE, {"home": "ru"}) == 1
