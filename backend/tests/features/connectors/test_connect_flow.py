"""The connect flow: one-time state bound to its browser, PKCE, the scope check, one grant per
provider account shared by its apps, an app moved to another account, and a workspace's
installation by its admin only (connectors plan §3.4)."""

import uuid
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select

from shosai.core.db.model_base import ModelBase
from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.authorize import NotOfferedError
from shosai.features.connectors.domain.catalogue import App, Provider
from shosai.features.connectors.domain.flows import challenge_of
from shosai.features.connectors.infrastructure.store.records import (
    ConnectionRecord,
    GrantRecord,
    GrantSecretRecord,
)
from tests.features.connectors.connect_bench import ConnectBench, connect_bench

__all__ = ["connect_bench"]


def someone() -> tuple[Home, uuid.UUID]:
    """A new person of the Russian home."""
    return Home.RU, uuid.uuid4()


def outcome(location: str) -> dict[str, str]:
    """The query of the cabinet's callback page."""
    assert location.startswith("/oauth/callback?")
    return {key: values[0] for key, values in parse_qs(urlsplit(location).query).items()}


async def rows(
    bench: ConnectBench, person: tuple[Home, uuid.UUID], model: type[ModelBase]
) -> list[Any]:
    """The person's rows of a table."""
    home, user_id = person
    async with bench.homes.transactions.begin(TenancyScope(home, user_id), read_only=True) as s:
        return list((await s.execute(select(model))).scalars().all())


async def events(bench: ConnectBench, home: Home) -> list[str]:
    """The event types written in the home."""
    async with bench.homes.transactions.begin(TenancyScope(home), read_only=True) as session:
        found = await session.execute(select(OutboxMessage.event_type).order_by(OutboxMessage.id))
        return list(found.scalars().all())


async def test_a_flow_connects_an_app_with_pkce_and_encrypted_tokens(
    connect_bench: ConnectBench,
) -> None:
    person = someone()
    handoff = await connect_bench.start(person, App.GOOGLE_CALENDAR)
    query = parse_qs(urlsplit(handoff.authorize_url).query)

    assert handoff.authorize_url.startswith("https://idp.test/authorize?")
    assert query["redirect_uri"] == ["https://shosai.test/v1/connectors/oauth/google/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["access_type"] == ["offline"]
    assert "https://www.googleapis.com/auth/calendar.events" in query["scope"][0]

    location = await connect_bench.finish(handoff, "ok:anna")

    assert outcome(location) == {"connector": "google_calendar", "status": "connected"}
    sent = parse_qs(connect_bench.provider.sent[-1].content.decode())
    assert challenge_of(sent["code_verifier"][0]) == query["code_challenge"][0]
    assert sent["client_secret"] == ["client-secret"]
    (grant,) = await rows(connect_bench, person, GrantRecord)
    assert (grant.external_account_id, grant.account_label) == ("anna", "anna@example.com")
    assert grant.provider_meta == {"tenant": "t-1"}
    (secret,) = await rows(connect_bench, person, GrantSecretRecord)
    assert connect_bench.keys.decrypt(secret.refresh_token_enc) == "refresh-anna"
    assert b"anna" not in secret.access_token_enc
    assert secret.expires_at is not None
    assert await events(connect_bench, Home.RU) == ["connectors.connection.connected"]


async def test_a_state_works_once_and_only_in_its_browser(connect_bench: ConnectBench) -> None:
    person = someone()
    stolen = await connect_bench.start(person, App.GOOGLE_CALENDAR)

    elsewhere = await connect_bench.finish(stolen, "ok:mallory", binder="another-browser")
    replayed = await connect_bench.finish(stolen, "ok:mallory")

    for location in (elsewhere, replayed):
        assert outcome(location) == {"status": "error", "error": "authorization_expired"}
    assert await rows(connect_bench, person, GrantRecord) == []


async def test_a_refusal_and_a_provider_s_own_error_are_told_apart(
    connect_bench: ConnectBench,
) -> None:
    person = someone()
    denied = await connect_bench.finish(
        await connect_bench.start(person, App.GOOGLE_DRIVE), None, error="access_denied"
    )
    consent = await connect_bench.finish(
        await connect_bench.start(person, App.GOOGLE_DRIVE), None, error="consent_required"
    )
    down = await connect_bench.finish(await connect_bench.start(person, App.GOOGLE_DRIVE), "down")

    assert outcome(denied)["status"] == "denied"
    assert outcome(consent)["error"] == "admin_consent_required"
    assert outcome(down)["error"] == "provider_unavailable"
    assert await rows(connect_bench, person, GrantRecord) == []


async def test_an_unticked_box_leaves_the_app_unconnected(connect_bench: ConnectBench) -> None:
    person = someone()

    location = await connect_bench.finish(
        await connect_bench.start(person, App.GOOGLE_CALENDAR), "short:anna"
    )

    assert outcome(location)["error"] == "scope_missing"
    assert await rows(connect_bench, person, ConnectionRecord) == []


async def test_apps_of_one_account_share_its_grant(connect_bench: ConnectBench) -> None:
    person = someone()
    await connect_bench.finish(await connect_bench.start(person, App.GOOGLE_CALENDAR), "ok:anna")
    await connect_bench.finish(await connect_bench.start(person, App.GOOGLE_DRIVE), "ok:anna")
    again = await connect_bench.finish(
        await connect_bench.start(person, App.GOOGLE_DRIVE), "ok:anna"
    )

    (grant,) = await rows(connect_bench, person, GrantRecord)
    connections = await rows(connect_bench, person, ConnectionRecord)
    assert {connection.app for connection in connections} == {"google_calendar", "google_drive"}
    assert {connection.grant_id for connection in connections} == {grant.id}
    assert "https://www.googleapis.com/auth/drive.file" in grant.granted_scopes
    assert "https://www.googleapis.com/auth/calendar.events" in grant.granted_scopes
    assert outcome(again)["status"] == "connected"
    (secret,) = await rows(connect_bench, person, GrantSecretRecord)
    assert secret.refresh_generation == 2


async def test_another_account_ends_the_app_s_old_connection(connect_bench: ConnectBench) -> None:
    person = someone()
    await connect_bench.finish(await connect_bench.start(person, App.GOOGLE_CALENDAR), "ok:anna")
    (first,) = await rows(connect_bench, person, ConnectionRecord)

    await connect_bench.finish(await connect_bench.start(person, App.GOOGLE_CALENDAR), "ok:work")

    (second,) = await rows(connect_bench, person, ConnectionRecord)
    assert second.id != first.id
    grants = {
        grant.external_account_id: grant for grant in await rows(connect_bench, person, GrantRecord)
    }
    assert grants["anna"].status == "revoking"
    assert grants["work"].status == "active"
    assert await events(connect_bench, Home.RU) == [
        "connectors.connection.connected", "connectors.connection.revoked",
        "connectors.connection.connected",
    ]  # fmt: skip


async def test_only_offered_apps_and_owners_start(connect_bench: ConnectBench) -> None:
    person = someone()
    with pytest.raises(NotOfferedError):
        await connect_bench.start(person, App.GMAIL)
    with pytest.raises(NotOfferedError):
        await connect_bench.start(person, App.GOOGLE_DRIVE, org_id=uuid.uuid4())


async def test_an_installation_belongs_to_its_workspace_and_needs_an_admin(
    connect_bench: ConnectBench,
) -> None:
    home, admin = someone()
    org = uuid.uuid4()
    refused = await connect_bench.finish(
        await connect_bench.start((home, admin), App.SLACK, org), "ok:team-1",
        provider=Provider.SLACK,
    )  # fmt: skip
    connect_bench.workspaces.admins[org] = {admin}

    location = await connect_bench.finish(
        await connect_bench.start((home, admin), App.SLACK, org), "ok:team-1",
        provider=Provider.SLACK,
    )  # fmt: skip

    assert outcome(refused) == {"flow": "chats", "status": "error", "error": "not_offered"}
    installed = outcome(location)
    assert (installed["flow"], installed["status"]) == ("chats", "connected")
    async with connect_bench.homes.transactions.begin(TenancyScope(home, admin, org)) as session:
        connection = (await session.execute(select(ConnectionRecord))).scalar_one()
    assert str(connection.id) == installed["installation_id"]
    assert connection.org_id == org
    (entry,) = connect_bench.workspaces.audit
    assert (entry.target_kind, entry.value) == ("integration", "slack:installed")
    assert await rows(connect_bench, (home, admin), ConnectionRecord) == []
