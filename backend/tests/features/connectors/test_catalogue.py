"""The catalogue of apps and the provider descriptor (connectors plan §3.2)."""

from dataclasses import replace
from datetime import timedelta

import pytest

from shosai.features.connectors.domain.catalogue import (
    CATALOGUE,
    App,
    AppSpec,
    AuthKind,
    Capability,
    Category,
    Owner,
    Provider,
    apps_of,
    spec_of,
)
from shosai.features.connectors.domain.descriptors import (
    LimitSubject,
    ProviderDescriptor,
    ProviderLimit,
    Revocation,
    RevocationKind,
    Timeouts,
    TokenAuth,
)


def test_every_app_of_the_owner_s_list_is_in_the_catalogue_once() -> None:
    assert set(CATALOGUE) == set(App)
    assert len(CATALOGUE) == 21
    assert {spec.app for spec in CATALOGUE.values()} == set(App)


def test_the_cabinet_s_categories_plus_calendar() -> None:
    assert {spec.category for spec in CATALOGUE.values()} == set(Category)
    calendars = {app for app, spec in CATALOGUE.items() if spec.category is Category.CALENDAR}
    assert calendars == {
        App.GOOGLE_CALENDAR, App.OUTLOOK_CALENDAR, App.YANDEX_CALENDAR, App.CALDAV,
    }  # fmt: skip


def test_gmail_has_its_own_google_application_and_the_others_share_one() -> None:
    google = {app: spec_of(app).client_key for app in apps_of(Provider.GOOGLE)}

    assert google == {
        App.GMAIL: "google_mail", App.GOOGLE_CALENDAR: "google", App.GOOGLE_DRIVE: "google",
    }  # fmt: skip


def test_drive_asks_only_for_files_the_person_picks() -> None:
    drive = spec_of(App.GOOGLE_DRIVE).scopes

    assert "https://www.googleapis.com/auth/drive.file" in drive
    assert not {scope for scope in drive if "drive.readonly" in scope or scope.endswith("/drive")}


def test_gmail_asks_for_modify_alone_among_restricted_scopes() -> None:
    gmail = {scope for scope in spec_of(App.GMAIL).scopes if "gmail" in scope}

    assert gmail == {"https://www.googleapis.com/auth/gmail.modify"}


def test_only_slack_installs_into_a_workspace() -> None:
    workspace = {app for app, spec in CATALOGUE.items() if Owner.WORKSPACE in spec.owners}

    assert workspace == {App.SLACK}
    slack = spec_of(App.SLACK)
    assert slack.scopes_for(Owner.WORKSPACE) != slack.scopes_for(Owner.PERSON)
    assert "users:read.email" in slack.scopes_for(Owner.WORKSPACE)


def test_secrets_without_oauth_and_mail_ru_with_a_password_fallback() -> None:
    kinds = {
        app: spec.auth for app, spec in CATALOGUE.items() if spec.auth[0] is not AuthKind.OAUTH2
    }

    assert kinds == {
        App.YANDEX_CALENDAR: (AuthKind.APP_LOGIN,), App.CALDAV: (AuthKind.APP_LOGIN,),
        App.AFFINITY: (AuthKind.API_KEY,), App.ZAPIER: (AuthKind.WEBHOOK_URL,),
    }  # fmt: skip
    assert spec_of(App.MAILRU_MAIL).auth == (AuthKind.OAUTH2, AuthKind.APP_LOGIN)


def test_an_app_spec_refuses_rights_without_oauth_and_a_bad_client_key() -> None:
    with pytest.raises(ValueError, match="OAuth"):
        AppSpec(App.CALDAV, "CalDAV", Provider.CALDAV, Capability.CALENDAR, Category.CALENDAR,
                (AuthKind.APP_LOGIN,), "caldav", frozenset({"calendar"}))  # fmt: skip
    with pytest.raises(ValueError, match="snake_case"):
        AppSpec(App.JIRA, "Jira", Provider.ATLASSIAN, Capability.TRACKER, Category.TASKS,
                (AuthKind.OAUTH2,), "Atlassian App")  # fmt: skip
    with pytest.raises(ValueError, match="способ входа"):
        AppSpec(App.JIRA, "Jira", Provider.ATLASSIAN, Capability.TRACKER, Category.TASKS, (),
                "atlassian")  # fmt: skip


BASE = ProviderDescriptor(
    provider=Provider.ATLASSIAN, client_key="atlassian",
    authorize_url="https://auth.example.com/authorize",
    token_url="https://auth.example.com/oauth/token", token_auth=TokenAuth.JSON, pkce=False,
    revocation=Revocation(RevocationKind.NONE),
)  # fmt: skip


def test_a_descriptor_takes_only_https_addresses_without_credentials() -> None:
    assert BASE.token_auth is TokenAuth.JSON
    for bad in ("http://auth.example.com/token", "https://user:pw@auth.example.com/token",
                "https:///token"):  # fmt: skip
        with pytest.raises(ValueError, match="HTTPS"):
            replace(BASE, token_url=bad)


def test_a_descriptor_keeps_the_core_s_own_authorize_parameters() -> None:
    assert replace(BASE, authorize_params=(("audience", "api.atlassian.com"),)).authorize_params
    with pytest.raises(ValueError, match="служебные"):
        replace(BASE, authorize_params=(("redirect_uri", "https://evil.example.com"),))


def test_a_descriptor_refuses_odd_separators_limits_and_concurrency() -> None:
    assert replace(BASE, scope_separator=",").scope_separator == ","
    with pytest.raises(ValueError, match="разделитель"):
        replace(BASE, scope_separator=";")
    limit = ProviderLimit("calls", LimitSubject.ACCOUNT, 10, timedelta(seconds=1))
    with pytest.raises(ValueError, match="дважды"):
        replace(BASE, limits=(limit, limit))
    with pytest.raises(ValueError, match="одновременных"):
        replace(BASE, concurrency_per_account=0)


def test_a_revocation_has_an_address_exactly_when_it_exists() -> None:
    assert Revocation(RevocationKind.ACCESS, "https://api.example.com/revoke").url
    with pytest.raises(ValueError, match="адрес отзыва"):
        Revocation(RevocationKind.NONE, "https://api.example.com/revoke")
    with pytest.raises(ValueError, match="адрес отзыва"):
        Revocation(RevocationKind.GRANT)


def test_limits_and_timeouts_are_positive_and_bounded() -> None:
    with pytest.raises(ValueError, match="положительные"):
        ProviderLimit("calls", LimitSubject.APPLICATION, 0, timedelta(minutes=1))
    with pytest.raises(ValueError, match="минуты"):
        Timeouts(read=timedelta(minutes=2))
