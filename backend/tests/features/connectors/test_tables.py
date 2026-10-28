"""Connectors' tables: a person's personal rows are theirs alone, a workspace's installation
follows the company policy, the database keeps the closed sets and one app per person, and a
person's part of export, transfer and erasure leaves the workspace's installations."""

import json
import uuid

import pytest
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import DBAPIError

from shosai.core.account_data.handlers import AccountRef
from shosai.core.db.model_base import ModelBase
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.account_data import ConnectorsAccountData
from shosai.features.connectors.infrastructure.store.records import (
    ConnectionRecord,
    GrantRecord,
    GrantSecretRecord,
)
from tests.harness.database_access import DatabaseAccess


def grant(person: uuid.UUID, org: uuid.UUID | None = None, **fields: object) -> dict[str, object]:
    """A Google grant of the person, personal unless a workspace is named."""
    return {
        "id": uuid.uuid4(), "user_id": person, "org_id": org, "provider": "google",
        "client_key": "google", "auth_kind": "oauth2", "external_account_id": str(uuid.uuid4()),
        "account_label": "anna@example.com", "granted_scopes": ["openid", "email"],
    } | fields  # fmt: skip


def secret(row: dict[str, object]) -> dict[str, object]:
    """The grant's ciphertexts."""
    return {
        "grant_id": row["id"], "user_id": row["user_id"], "org_id": row["org_id"],
        "access_token_enc": b"access-cipher", "refresh_token_enc": b"refresh-cipher",
    }  # fmt: skip


def connection(row: dict[str, object], app: str = "google_calendar") -> dict[str, object]:
    """An app on the grant."""
    return {
        "id": uuid.uuid4(), "user_id": row["user_id"], "org_id": row["org_id"], "app": app,
        "grant_id": row["id"],
    }  # fmt: skip


async def write(
    homes: DatabaseAccess,
    scope: TenancyScope,
    model: type[ModelBase],
    rows: list[dict[str, object]],
) -> None:
    """Insert rows in one transaction of the scope."""
    async with homes.transactions.begin(scope) as session:
        await session.execute(insert(model), rows)


async def seed(homes: DatabaseAccess, scope: TenancyScope, row: dict[str, object]) -> None:
    """A grant, its secrets and one app on it."""
    await write(homes, scope, GrantRecord, [row])
    await write(homes, scope, GrantSecretRecord, [secret(row)])
    await write(homes, scope, ConnectionRecord, [connection(row)])


async def count(homes: DatabaseAccess, scope: TenancyScope, model: type[ModelBase]) -> int:
    """The rows of a table the scope sees."""
    async with homes.transactions.begin(scope, read_only=True) as session:
        return len((await session.execute(select(model))).all())


async def test_a_personal_grant_is_its_person_s_alone(homes: DatabaseAccess) -> None:
    person, other = uuid.uuid4(), uuid.uuid4()
    mine, theirs = TenancyScope(Home.RU, person), TenancyScope(Home.RU, other)
    row = grant(person)
    await seed(homes, mine, row)

    assert await count(homes, mine, GrantRecord) == 1
    for model in (GrantRecord, GrantSecretRecord, ConnectionRecord):
        assert await count(homes, theirs, model) == 0
    with pytest.raises(DBAPIError):
        await write(homes, theirs, GrantRecord, [grant(person)])
    async with homes.transactions.begin(theirs) as session:
        await session.execute(update(GrantRecord).values(account_label="stolen"))
    async with homes.transactions.begin(mine, read_only=True) as session:
        labels = (await session.execute(select(GrantRecord.account_label))).scalars().all()
    assert labels == ["anna@example.com"]


async def test_an_installation_follows_its_workspace(homes: DatabaseAccess) -> None:
    admin, org = uuid.uuid4(), uuid.uuid4()
    workspace = TenancyScope(Home.RU, admin, org)
    await seed(homes, workspace, grant(admin, org, provider="slack", client_key="slack"))

    assert await count(homes, TenancyScope(Home.RU, uuid.uuid4(), org), ConnectionRecord) == 1
    assert await count(homes, TenancyScope(Home.RU, admin), ConnectionRecord) == 0
    with pytest.raises(DBAPIError):
        await write(homes, TenancyScope(Home.RU, admin), GrantRecord, [grant(admin, uuid.uuid4())])


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "needs_reconnect"},
        {"status": "active", "problem": "refresh_refused"},
        {"provider": "nango"},
        {"auth_kind": "password"},
        {"client_key": "Google App"},
        {"external_account_id": ""},
    ],
)
async def test_the_database_keeps_the_closed_sets(
    homes: DatabaseAccess, fields: dict[str, object]
) -> None:
    person = uuid.uuid4()
    with pytest.raises(DBAPIError):
        await write(homes, TenancyScope(Home.RU, person), GrantRecord, [grant(person) | fields])


async def test_one_account_per_app_and_apps_on_their_own_person_s_grant(
    homes: DatabaseAccess,
) -> None:
    person, other = uuid.uuid4(), uuid.uuid4()
    scope = TenancyScope(Home.RU, person)
    first, second = grant(person), grant(person)
    await seed(homes, scope, first)
    await write(homes, scope, GrantRecord, [second])

    with pytest.raises(DBAPIError):
        await write(homes, scope, ConnectionRecord, [connection(second)])
    with pytest.raises(DBAPIError):
        await write(
            homes, scope, ConnectionRecord, [connection(first, app="notion") | {"app": "x"}]
        )
    foreign = connection(first, app="google_drive") | {"user_id": other}
    with pytest.raises(DBAPIError):
        await write(homes, TenancyScope(Home.RU, other), ConnectionRecord, [foreign])
    empty = secret(second) | {"access_token_enc": None, "refresh_token_enc": None}
    with pytest.raises(DBAPIError):
        await write(homes, scope, GrantSecretRecord, [empty])


async def test_a_grant_s_secrets_go_with_it(homes: DatabaseAccess) -> None:
    person = uuid.uuid4()
    scope = TenancyScope(Home.RU, person)
    row = grant(person)
    await write(homes, scope, GrantRecord, [row])
    await write(homes, scope, GrantSecretRecord, [secret(row)])

    async with homes.transactions.begin(scope) as session:
        await session.execute(delete(GrantRecord).where(GrantRecord.id == row["id"]))

    assert await count(homes, scope, GrantSecretRecord) == 0


async def export_text(handler: ConnectorsAccountData, account: AccountRef) -> dict[str, str]:
    """The export's files and their text."""
    files: dict[str, str] = {}
    async for item in handler.export(account):
        files[item.name] = b"".join([chunk async for chunk in item.chunks]).decode()
    return files


async def test_the_person_s_part_moves_and_goes_but_installations_stay(
    homes: DatabaseAccess,
) -> None:
    person, org = uuid.uuid4(), uuid.uuid4()
    handler = ConnectorsAccountData(homes.transactions)
    account = AccountRef(person, Home.RU)
    await seed(homes, TenancyScope(Home.RU, person), grant(person))
    installation = grant(person, org, provider="slack", client_key="slack")
    await seed(homes, TenancyScope(Home.RU, person, org), installation)

    exported = await export_text(handler, account)
    assert set(exported) == {
        "connector_grants.jsonl", "connector_grant_secrets.jsonl", "connections.jsonl",
    }  # fmt: skip
    assert "cipher" not in json.dumps(exported)
    assert json.loads(exported["connector_grants.jsonl"])["account_label"] == "anna@example.com"

    await handler.copy(account, Home.EU)
    await handler.copy(account, Home.EU)
    moved = AccountRef(person, Home.EU)
    assert await handler.manifest(moved) == await handler.manifest(account)
    eu = TenancyScope(Home.EU, person)
    async with homes.transactions.begin(eu, read_only=True) as session:
        kept = (await session.execute(select(GrantSecretRecord.refresh_token_enc))).scalars().all()
    assert kept == [b"refresh-cipher"]

    await handler.erase(account)
    await handler.erase(account)
    assert await handler.remains(account) == ()
    assert await count(homes, TenancyScope(Home.RU, person, org), ConnectionRecord) == 1
    await handler.purge(moved)
    assert await handler.remains(moved) == ()
