"""The rules of a connect flow and of a refresh (connectors plan §3.4, §3.5)."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.connectors.domain.flows import (
    CALLBACK_PAGE,
    FlowError,
    Outcome,
    ReturnKind,
    ReturnPathError,
    ReturnTarget,
    binder_matches,
    callback_location,
    challenge_of,
    digest_of,
    new_binder,
    new_nonce,
    new_verifier,
)
from shosai.features.connectors.domain.refresh import (
    KEEPALIVE_FLOOR,
    RefreshOutcome,
    classify_refresh,
    keepalive_at,
    needs_refresh,
)

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
POPUP = ReturnTarget(ReturnKind.POPUP)


def test_the_s256_challenge_matches_rfc_7636() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

    assert challenge_of(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    with pytest.raises(ValueError, match="PKCE"):
        challenge_of("short")


def test_new_secrets_are_long_unique_and_valid() -> None:
    verifier = new_verifier()

    assert 43 <= len(verifier) <= 128
    assert challenge_of(verifier)
    assert len({new_nonce() for _ in range(50)}) == 50
    assert len(new_binder()) >= 43


def test_the_binder_matches_only_its_own_browser() -> None:
    binder = new_binder()
    kept = digest_of(binder)

    assert binder_matches(kept, binder)
    assert not binder_matches(kept, new_binder())
    assert not binder_matches(kept, None)


def test_the_popup_returns_to_the_callback_page_with_codes() -> None:
    connected = callback_location(POPUP, "gmail", Outcome.CONNECTED)
    failed = callback_location(POPUP, "jira", Outcome.ERROR, error=FlowError.SCOPE_MISSING)

    assert connected == f"{CALLBACK_PAGE}?connector=gmail&status=connected"
    assert parse_qs(urlsplit(failed).query) == {
        "connector": ["jira"], "status": ["error"], "error": ["scope_missing"],
    }  # fmt: skip
    with pytest.raises(ValueError, match="error"):
        callback_location(POPUP, "gmail", Outcome.DENIED, error=FlowError.SCOPE_MISSING)


def test_chats_gets_its_flow_and_the_installation_id() -> None:
    target = ReturnTarget(ReturnKind.CHATS)

    connected = callback_location(target, "slack", Outcome.CONNECTED, connection_id="c-1")
    denied = callback_location(target, "slack", Outcome.DENIED, connection_id="c-1")

    assert connected == f"{CALLBACK_PAGE}?flow=chats&status=connected&installation_id=c-1"
    assert denied == f"{CALLBACK_PAGE}?flow=chats&status=denied"


def test_a_page_return_stays_inside_the_cabinet() -> None:
    page = ReturnTarget(ReturnKind.PAGE, "/app/knowledge-base?tab=sources")

    location = callback_location(page, "google_drive", Outcome.CONNECTED)

    assert location == "/app/knowledge-base?tab=sources&connector=google_drive&status=connected"
    for bad in ("https://evil.example.com/app", "//evil.example.com", "/app/../admin",
                "/admin/users", "/app\\evil", "/app/x?next=//evil"):  # fmt: skip
        with pytest.raises(ReturnPathError):
            ReturnTarget(ReturnKind.PAGE, bad)
    with pytest.raises(ReturnPathError):
        ReturnTarget(ReturnKind.POPUP, "/app")


@given(path=st.text(max_size=80))
def test_every_accepted_return_path_is_relative_to_the_cabinet(path: str) -> None:
    try:
        target = ReturnTarget(ReturnKind.PAGE, path)
    except ReturnPathError:
        return
    assert target.path is not None
    assert target.path.startswith("/app")
    assert "//" not in target.path
    assert not urlsplit(target.path).netloc


def test_a_token_expiring_within_two_minutes_is_refreshed_first() -> None:
    assert needs_refresh(NOW + timedelta(seconds=119), NOW)
    assert not needs_refresh(NOW + timedelta(minutes=3), NOW)
    assert not needs_refresh(None, NOW)


@pytest.mark.parametrize(
    ("status", "code", "outcome"),
    [
        (200, None, RefreshOutcome.REFRESHED),
        (400, "invalid_grant", RefreshOutcome.GRANT_REFUSED),
        (401, "unauthorized_client", RefreshOutcome.GRANT_REFUSED),
        (400, None, RefreshOutcome.GRANT_REFUSED),
        (401, "invalid_client", RefreshOutcome.CLIENT_MISCONFIGURED),
        (400, "unsupported_grant_type", RefreshOutcome.CLIENT_MISCONFIGURED),
        (200, "invalid_grant", RefreshOutcome.GRANT_REFUSED),
        (429, None, RefreshOutcome.TRANSIENT),
        (503, "temporarily_unavailable", RefreshOutcome.TRANSIENT),
        (None, None, RefreshOutcome.TRANSIENT),
        (409, None, RefreshOutcome.TRANSIENT),
    ],
)
def test_a_token_endpoint_s_answer_falls_into_one_class(
    status: int | None, code: str | None, outcome: RefreshOutcome
) -> None:
    assert classify_refresh(status, code) is outcome


@given(days=st.integers(1, 400), spread=st.floats(-1.0, 1.0))
def test_a_keep_alive_comes_before_the_provider_forgets_an_idle_grant(
    days: int, spread: float
) -> None:
    idle = timedelta(days=days)

    planned = keepalive_at(NOW, idle, spread)

    assert planned is not None
    assert NOW + min(KEEPALIVE_FLOOR, idle) <= planned
    assert planned < NOW + idle or idle <= KEEPALIVE_FLOOR


def test_a_grant_that_never_expires_unused_has_no_keep_alive() -> None:
    assert keepalive_at(NOW, None) is None
    ninety = keepalive_at(NOW, timedelta(days=90))
    assert ninety == NOW + timedelta(days=76)
    with pytest.raises(ValueError, match="разброс"):
        keepalive_at(NOW, timedelta(days=90), 1.5)
