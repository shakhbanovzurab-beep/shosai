"""When a grant refreshes, what a token endpoint's answer means, and when to keep it alive.

Refresh is lazy: a session refreshes an access token that expires within two minutes, and
once more on a 401. A token endpoint's answer falls into four classes (plan §3.5): a new
token; a refusal of the grant (`invalid_grant` and its kin), after which only the person
can repair it; a refusal of Shosai's own application (`invalid_client`), which is an alert
and breaks no grant — the draft left such rows locked; and a transient failure (5xx,
network, 429), which changes nothing. A refresh token that dies when unused is refreshed by
a keep-alive two weeks before the provider's idle expiry, jittered so the scheduler's ticks
do not pile up.
"""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

REFRESH_MARGIN: Final = timedelta(minutes=2)
KEEPALIVE_MARGIN: Final = timedelta(days=14)
KEEPALIVE_JITTER: Final = timedelta(days=2)
# Самый короткий срок, на который keep-alive вообще планируется: тестовый проект Google (7 дней).
KEEPALIVE_FLOOR: Final = timedelta(hours=12)
HTTP_SUCCESS: Final = range(200, 300)
HTTP_TOO_MANY: Final = 429
HTTP_SERVER_ERRORS: Final = range(500, 600)
# 400, 401 и 403 без понятного кода: провайдер отказал этому гранту, повтор не поможет.
HTTP_GRANT_REFUSALS: Final = frozenset({400, 401, 403})

# RFC 6749 §5.2 и то, как провайдеры называют отказ в гранте.
_GRANT_REFUSALS: Final = frozenset({
    "invalid_grant", "unauthorized_client", "access_denied", "invalid_token", "token_revoked",
    "token_expired", "invalid_refresh_token", "refresh_token_expired",
})  # fmt: skip
_CLIENT_REFUSALS: Final = frozenset({"invalid_client", "unsupported_grant_type"})


class RefreshOutcome(StrEnum):
    """What a token endpoint's answer means for the grant."""

    REFRESHED = "refreshed"
    GRANT_REFUSED = "grant_refused"
    CLIENT_MISCONFIGURED = "client_misconfigured"
    TRANSIENT = "transient"


def needs_refresh(expires_at: datetime | None, now: datetime) -> bool:
    """Whether an access token must be refreshed before use; a token without expiry never."""
    return expires_at is not None and expires_at - REFRESH_MARGIN <= now


def classify_refresh(status: int | None, error_code: str | None) -> RefreshOutcome:
    """The class of a token endpoint's answer: `status` is None when no answer came."""
    if status is None or status == HTTP_TOO_MANY or status in HTTP_SERVER_ERRORS:
        return RefreshOutcome.TRANSIENT
    if status in HTTP_SUCCESS and error_code is None:
        return RefreshOutcome.REFRESHED
    code = (error_code or "").strip().lower()
    if code in _CLIENT_REFUSALS:
        return RefreshOutcome.CLIENT_MISCONFIGURED
    if code in _GRANT_REFUSALS:
        return RefreshOutcome.GRANT_REFUSED
    if status in HTTP_GRANT_REFUSALS:
        return RefreshOutcome.GRANT_REFUSED
    return RefreshOutcome.TRANSIENT


def keepalive_at(
    refreshed_at: datetime, idle_expiry: timedelta | None, spread: float = 0.0
) -> datetime | None:
    """When an idle grant must be refreshed to stay alive; None when it never expires unused.

    `spread` in [-1, 1] moves the moment within the jitter; the caller draws it at random.
    """
    if idle_expiry is None:
        return None
    lead = KEEPALIVE_MARGIN if idle_expiry > 2 * KEEPALIVE_MARGIN else idle_expiry / 2
    jitter_span = min(KEEPALIVE_JITTER, lead / 4)
    if not -1.0 <= spread <= 1.0:
        message = "разброс keep-alive — от −1 до 1"
        raise ValueError(message)
    jitter = jitter_span * spread
    return refreshed_at + max(idle_expiry - lead + jitter, KEEPALIVE_FLOOR)
