"""The session cookies of the draft, which shipped clients keep in their cookie jars.

`meetassist_refresh` holds the refresh token: httpOnly, only for `/v1/auth`. The CSRF
value sits in `meetassist_csrf`, readable by scripts on `/`, and the cabinet repeats it in
`X-CSRF-Token` on refresh (double submit). The value is created at sign-in and kept by
every refresh: rotating it signed tabs out at random (draft commit 18ab7bf67).
"""

from dataclasses import dataclass
from typing import Final

from starlette.responses import Response

from shosai.features.identity.domain.tokens import REFRESH_TOKEN_LIFETIME

REFRESH_COOKIE: Final = "meetassist_refresh"
CSRF_COOKIE: Final = "meetassist_csrf"
CSRF_HEADER: Final = "X-CSRF-Token"
CLIENT_KIND_HEADER: Final = "X-Client-Kind"
REFRESH_PATH: Final = "/v1/auth"
MAX_AGE: Final = int(REFRESH_TOKEN_LIFETIME.total_seconds())


@dataclass(frozen=True, slots=True)
class CookiePolicy:
    """Where the cookies apply: secure outside local development, an optional domain."""

    secure: bool
    domain: str | None


def set_session_cookies(
    response: Response, policy: CookiePolicy, refresh_token: str, csrf_token: str
) -> None:
    """Write the refresh and CSRF cookies of a session."""
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, max_age=MAX_AGE, path=REFRESH_PATH,
        domain=policy.domain, secure=policy.secure, httponly=True, samesite="lax",
    )  # fmt: skip
    response.set_cookie(
        CSRF_COOKIE, csrf_token, max_age=MAX_AGE, path="/",
        domain=policy.domain, secure=policy.secure, httponly=False, samesite="lax",
    )  # fmt: skip


def clear_session_cookies(response: Response, policy: CookiePolicy) -> None:
    """Delete both cookies."""
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_PATH, domain=policy.domain, secure=policy.secure,
        httponly=True, samesite="lax",
    )  # fmt: skip
    response.delete_cookie(
        CSRF_COOKIE, path="/", domain=policy.domain, secure=policy.secure, samesite="lax"
    )
