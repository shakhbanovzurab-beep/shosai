"""Atlassian's rules without a database: the report's cycle, batches and verdicts, the quota
headers, the redirect URI and an application configured whole or not at all."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr, ValidationError

from shosai.features.connectors.domain.account_report import (
    ReportedAccount,
    accounts_of,
    batches,
    cycle_of,
    rfc3339,
)
from shosai.features.connectors.domain.catalogue import Provider
from shosai.features.connectors.domain.descriptors import (
    ProviderDescriptor,
    Revocation,
    RevocationKind,
    TokenAuth,
)
from shosai.features.connectors.infrastructure.oauth.urls import callback_uri
from shosai.features.connectors.infrastructure.providers.atlassian import ATLASSIAN
from shosai.features.connectors.infrastructure.providers.atlassian_report import verdicts_of
from shosai.features.connectors.infrastructure.providers.configured import configured_clients
from shosai.features.connectors.infrastructure.transport.quota import near_quota, quota_used
from shosai.features.connectors.settings import ConnectorsSettings

MOMENT = datetime(2026, 10, 28, 12, 30, 15, 123456, tzinfo=UTC)


def test_the_cycle_comes_from_the_header_when_it_means_one() -> None:
    assert cycle_of("604800") == timedelta(days=7)
    assert [cycle_of(value) for value in (None, "", "soon", "0", "-5")] == [None] * 5


def test_accounts_are_reported_once_each_in_requests_of_ninety() -> None:
    held = [ReportedAccount(f"a-{n:03}", MOMENT) for n in range(181)]
    later = ReportedAccount("a-000", MOMENT + timedelta(days=1))

    accounts = accounts_of([*held, later])

    assert [len(batch) for batch in batches(accounts)] == [90, 90, 1]
    assert accounts[0] == later
    assert rfc3339(MOMENT) == "2026-10-28T12:30:15Z"
    assert rfc3339(MOMENT.replace(tzinfo=None)) == "2026-10-28T12:30:15Z"


def test_only_known_verdicts_are_read() -> None:
    body = {"accounts": [
        {"accountId": "a-1", "status": "closed"}, {"accountId": "a-2", "status": "updated"},
        {"accountId": "a-3", "status": "archived"}, {"status": "closed"}, "noise",
    ]}  # fmt: skip

    assert {key: value.value for key, value in verdicts_of(body).items()} == {
        "a-1": "closed", "a-2": "updated",
    }  # fmt: skip
    assert verdicts_of([]) == {}


def test_an_answer_past_eighty_percent_of_the_quota_is_near_it() -> None:
    policy = {"Beta-RateLimit-Policy": '"global-app-quota";q=65000;w=3600'}

    near = {**policy, "Beta-RateLimit": '"global-app-quota";r=12000;t=600'}
    far = {**policy, "Beta-RateLimit": '"global-app-quota";r=20000;t=600'}
    enforced = {"RateLimit-Policy": '"p";q=100;w=3600', "RateLimit": '"p";r=10;t=60'}

    assert near_quota(near)
    assert near_quota(enforced)
    assert [near_quota(headers) for headers in (far, policy, {})] == [False] * 3
    assert quota_used(enforced) == pytest.approx(0.9)


def test_atlassian_returns_to_the_draft_s_registered_callback() -> None:
    assert callback_uri("https://shosai.test/", ATLASSIAN) == (
        "https://shosai.test/v1/jira/oauth/callback"
    )
    assert ATLASSIAN.rotating_refresh
    assert ATLASSIAN.revocation.kind is RevocationKind.NONE
    with pytest.raises(ValueError, match="обратный путь"):
        ProviderDescriptor(
            provider=Provider.NOTION, client_key="notion", authorize_url="https://n.test/a",
            token_url="https://n.test/t", token_auth=TokenAuth.BASIC_JSON, pkce=False,
            revocation=Revocation(RevocationKind.NONE), redirect_path="/v1/../admin",
        )  # fmt: skip


def test_an_application_is_configured_whole_or_not_at_all() -> None:
    whole = ConnectorsSettings(
        connectors_atlassian_client_id="id", connectors_atlassian_client_secret=SecretStr("s")
    )

    assert set(configured_clients(whole)) == {"atlassian"}
    assert configured_clients(ConnectorsSettings()) == {}
    with pytest.raises(ValidationError, match="CLIENT_SECRET"):
        ConnectorsSettings(connectors_atlassian_client_id="id")
