"""Google's rules without a database: scopes as the catalogue names them, its own callback
errors, and the two applications configured with Testing's seven-day consents."""

from datetime import UTC, datetime, timedelta

from pydantic import SecretStr

from shosai.features.connectors.domain.flows import FlowError
from shosai.features.connectors.infrastructure.providers.configured import configured_clients
from shosai.features.connectors.infrastructure.providers.google import (
    GOOGLE,
    GOOGLE_MAIL,
    GoogleAdapter,
)
from shosai.features.connectors.settings import ConnectorsSettings

NOW = datetime(2026, 10, 28, tzinfo=UTC)


def test_openid_scopes_are_read_back_by_their_short_names() -> None:
    payload = {
        "access_token": "a", "expires_in": 3599,
        "scope": "openid https://www.googleapis.com/auth/userinfo.email "
        "https://www.googleapis.com/auth/drive.file",
    }  # fmt: skip

    tokens = GoogleAdapter(GOOGLE).tokens(payload, NOW)

    assert tokens.scopes == frozenset(
        {"openid", "email", "https://www.googleapis.com/auth/drive.file"}
    )
    assert tokens.expires_at == NOW + timedelta(seconds=3599)


def test_a_workspace_block_is_an_admin_s_to_lift() -> None:
    adapter = GoogleAdapter(GOOGLE)

    assert adapter.callback_error("admin_policy_enforced", None) is FlowError.ADMIN_CONSENT_REQUIRED
    assert adapter.callback_error("org_internal", None) is FlowError.NOT_OFFERED
    assert adapter.callback_error("access_denied", None) is None


def test_the_two_projects_share_google_s_rules_but_not_their_quotas() -> None:
    assert (GOOGLE_MAIL.client_key, GOOGLE_MAIL.token_url) == ("google_mail", GOOGLE.token_url)
    assert dict(GOOGLE.authorize_params) == {
        "access_type": "offline", "include_granted_scopes": "true", "prompt": "consent",
    }  # fmt: skip
    assert GOOGLE.reports_granted_scopes
    assert not GOOGLE.rotating_refresh
    assert [limit.name for limit in GOOGLE_MAIL.limits] == ["units"]
    assert GOOGLE_MAIL.concurrency_per_account == 5


def test_shosai_mail_is_in_testing_unless_the_deployment_says_otherwise() -> None:
    settings = ConnectorsSettings(
        connectors_google_client_id="main", connectors_google_client_secret=SecretStr("m"),
        connectors_google_mail_client_id="mail",
        connectors_google_mail_client_secret=SecretStr("s"),
    )  # fmt: skip

    clients = configured_clients(settings)

    assert set(clients) == {"google", "google_mail"}
    assert clients["google"].consent_lifetime is None
    assert clients["google_mail"].consent_lifetime == timedelta(days=7)
    staging = configured_clients(settings.model_copy(update={"connectors_google_testing": True}))
    assert staging["google"].consent_lifetime == timedelta(days=7)
