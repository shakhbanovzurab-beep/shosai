"""The Jira grant against Atlassian's recorded answers (connectors plan step 8): a connect at the
registered callback keeps the sites; every refresh keeps the rotated token; a reused one breaks
the grant; the personal data report erases a closed account and rereads a changed one."""

import uuid
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select, update

from shosai.core.events.records import OutboxMessage
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.contracts import NeedsReconnectError
from shosai.features.connectors.contracts.provider import ProviderUnavailableError
from shosai.features.connectors.domain.states import Problem
from shosai.features.connectors.infrastructure.metrics import ACCOUNTS_REPORTED
from shosai.features.connectors.infrastructure.store.records import (
    ConnectionRecord,
    GrantRecord,
    GrantSecretRecord,
)
from tests.features.billing.people_bench import bearer
from tests.features.connectors.atlassian_bench import JIRA_SCOPES, AtlassianBench, atlassian
from tests.features.connectors.connect_bench import BASE_URL

__all__ = ["atlassian"]

type Person = tuple[Home, uuid.UUID]


def someone() -> Person:
    """A new person in the Russian home."""
    return Home.RU, uuid.uuid4()


async def connected(bench: AtlassianBench, person: Person, account: str) -> uuid.UUID:
    """Connect Jira through the routes as the person; the grant's id."""
    started = await bench.http.post(
        "/v1/connectors/jira/authorize", json={}, headers=bearer(person)
    )
    state = parse_qs(urlsplit(started.json()["authorize_url"]).query)["state"][0]
    done = await bench.http.get(
        "/v1/jira/oauth/callback", params={"state": state, "code": f"ok:{account}"}
    )
    assert done.headers["location"] == "/oauth/callback?connector=jira&status=connected"
    async with bench.homes.transactions.begin(TenancyScope(*person), read_only=True) as session:
        grant_id: uuid.UUID | None = await session.scalar(select(GrantRecord.id))
    assert grant_id is not None
    return grant_id


async def grant_of(bench: AtlassianBench, person: Person) -> GrantRecord | None:
    """The person's grant, if any."""
    async with bench.homes.transactions.begin(TenancyScope(*person), read_only=True) as session:
        return await session.scalar(select(GrantRecord))


async def expire(bench: AtlassianBench, person: Person, grant_id: uuid.UUID) -> None:
    """Make the grant's access token one that must be refreshed."""
    async with bench.homes.transactions.begin(TenancyScope(*person)) as session:
        await session.execute(
            update(GrantSecretRecord)
            .where(GrantSecretRecord.grant_id == grant_id)
            .values(expires_at=GrantSecretRecord.refreshed_at - timedelta(hours=1))
        )


async def test_jira_connects_at_its_registered_callback_and_keeps_the_sites(
    atlassian: AtlassianBench,
) -> None:
    person = someone()
    started = await atlassian.http.post(
        "/v1/connectors/jira/authorize", json={}, headers=bearer(person)
    )
    query = parse_qs(urlsplit(started.json()["authorize_url"]).query)
    cookie = started.headers["set-cookie"]
    await connected(atlassian, person, "anna")

    assert (query["audience"], query["prompt"]) == (["api.atlassian.com"], ["consent"])
    assert query["redirect_uri"] == [f"{BASE_URL}/v1/jira/oauth/callback"]
    assert query["code_challenge_method"] == ["S256"]
    # Браузер вернёт привязку только на путь колбэка, зарегистрированный у Atlassian.
    assert "Path=/v1/jira/oauth/callback" in cookie
    assert set(query["scope"][0].split()) == set(JIRA_SCOPES.split())
    exchange = atlassian.atlassian.token_requests[0]
    assert exchange["redirect_uri"] == f"{BASE_URL}/v1/jira/oauth/callback"
    assert (exchange["client_id"], exchange["client_secret"]) == (
        "atlassian-client", "atlassian-secret",
    )  # fmt: skip
    assert exchange["code_verifier"]
    grant = await grant_of(atlassian, person)
    assert grant is not None
    assert (grant.external_account_id, grant.account_label) == ("anna", "anna@example.com")
    assert grant.provider_meta["sites"] == [
        {"cloud_id": "cloud-anna", "name": "anna", "url": "https://anna.atlassian.net"}
    ]
    assert "profile_at" in grant.provider_meta


async def test_every_refresh_keeps_the_rotated_token_and_a_reused_one_breaks_the_grant(
    atlassian: AtlassianBench,
) -> None:
    person = someone()
    grant_id = await connected(atlassian, person, "anna")
    scope = TenancyScope(*person)

    await expire(atlassian, person, grant_id)
    first = await atlassian.tokens.access(scope, grant_id)
    await expire(atlassian, person, grant_id)
    second = await atlassian.tokens.access(scope, grant_id)
    # Текущий токен обновления израсходовал кто-то вне Shosai: Atlassian его больше не примет.
    atlassian.atlassian.live_refresh.clear()
    await expire(atlassian, person, grant_id)
    with pytest.raises(NeedsReconnectError) as broken:
        await atlassian.tokens.access(scope, grant_id)

    refreshes = [
        r for r in atlassian.atlassian.token_requests if r["grant_type"] != "authorization_code"
    ]
    assert [r["refresh_token"] for r in refreshes] == ["ref-1", "ref-2", "ref-3"]
    assert (first.get_secret_value(), second.get_secret_value()) == ("acc-2", "acc-3")
    assert broken.value.problem is Problem.REFRESH_REFUSED
    grant = await grant_of(atlassian, person)
    assert grant is not None
    assert (grant.status, grant.problem) == ("needs_reconnect", "refresh_refused")


async def test_the_report_erases_a_closed_account_and_rereads_a_changed_one(
    atlassian: AtlassianBench,
) -> None:
    kept, closed, changed = someone(), someone(), someone()
    for person, account in ((kept, "kept-1"), (closed, "closed-1"), (changed, "changed-1")):
        await connected(atlassian, person, account)
    atlassian.atlassian.verdicts = [
        {"accountId": "closed-1", "status": "closed"},
        {"accountId": "changed-1", "status": "updated"},
    ]
    atlassian.atlassian.emails["changed-1"] = "changed@example.com"

    await atlassian.accounts.report(Home.RU)

    (sent,) = atlassian.atlassian.reports
    assert sorted(item["accountId"] for item in sent["accounts"]) == [
        "changed-1", "closed-1", "kept-1",
    ]  # fmt: skip
    assert all(item["updatedAt"].endswith("Z") for item in sent["accounts"])
    assert await grant_of(atlassian, closed) is None
    async with atlassian.homes.transactions.begin(TenancyScope(*closed), read_only=True) as s:
        assert await s.scalar(select(ConnectionRecord.id)) is None
    rereads = await grant_of(atlassian, changed)
    assert rereads is not None
    assert rereads.account_label == "changed@example.com"
    async with atlassian.homes.transactions.begin(TenancyScope(Home.RU), read_only=True) as s:
        revoked = (await s.scalars(
            select(OutboxMessage.payload).where(
                OutboxMessage.event_type == "connectors.connection.revoked"
            )
        )).all()  # fmt: skip
    assert [payload["reason"] for payload in revoked] == ["provider_closed"]
    sample = atlassian.counters.get_sample_value
    labels = {"provider": "atlassian"}
    assert sample(ACCOUNTS_REPORTED, {**labels, "verdict": "reported"}) == 3
    assert sample(ACCOUNTS_REPORTED, {**labels, "verdict": "closed"}) == 1


async def test_a_report_takes_another_person_s_token_and_waits_out_an_outage(
    atlassian: AtlassianBench,
) -> None:
    first, second = someone(), someone()
    await connected(atlassian, first, "a-1")
    await connected(atlassian, second, "a-2")
    home = TenancyScope(Home.RU)
    async with atlassian.workers.begin(home, read_only=True, sweep=True) as s:
        leading = await s.scalar(
            select(GrantRecord.external_account_id).order_by(GrantRecord.id).limit(1)
        )
    tokens = {account: token for token, account in atlassian.atlassian.accounts.items()}
    atlassian.atlassian.refused_reporters = {tokens[str(leading)]}

    await atlassian.accounts.report(Home.RU)
    atlassian.atlassian.report_status = 503
    with pytest.raises(ProviderUnavailableError):
        await atlassian.accounts.report(Home.RU)

    refused, taken = atlassian.atlassian.reports[:2]
    assert refused["token"] == tokens[str(leading)]
    assert taken["token"] != refused["token"]
    assert len(taken["accounts"]) == 2
