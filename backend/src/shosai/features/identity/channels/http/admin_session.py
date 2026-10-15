"""The admin's session: `POST`, `GET` and `DELETE /v1/admin/session` (ADR 0049).

The cookie `shosai_admin` is HttpOnly, SameSite=Strict and sent only to `/v1/admin`, so
no script reads it and no other site's page sends it; it lives 8 hours and signing out
ends it on the server at once.
"""

from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import APIRouter, Cookie, Depends
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request
from starlette.responses import Response

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import client_address, rate_limited
from shosai.features.identity.application.admin_access import AdminAccess
from shosai.features.identity.channels.http.cookies import CookiePolicy
from shosai.features.identity.contracts import ADMIN_COOKIE, ADMIN_COOKIE_LENGTH, require_admin
from shosai.features.identity.domain.admin_credentials import MAX_ADMIN_USERNAME_LENGTH
from shosai.features.identity.domain.passwords import MAX_PASSWORD_LENGTH
from shosai.features.identity.infrastructure.admin_sessions import ADMIN_SESSION_LIFETIME

SIGN_IN_LIMIT: Final = RateLimit("identity.admin_sign_in_address", 5, timedelta(minutes=15), 5)
ADMIN_PATH: Final = "/v1/admin"


class AdminSignInRequest(BaseModel):
    """The admin's login and password."""

    model_config = ConfigDict(extra="forbid")

    username: Annotated[str, Field(min_length=1, max_length=MAX_ADMIN_USERNAME_LENGTH)]
    password: Annotated[str, Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)]


def build_admin_session_router(
    access: AdminAccess, ports: PortDirectory, limiter: RateLimiter, cookies: CookiePolicy
) -> APIRouter:
    """Sign the admin in, tell whether they are signed in, sign them out."""
    router = APIRouter(prefix=f"{ADMIN_PATH}/session", tags=["admin"])

    @router.post(
        "",
        status_code=HTTPStatus.NO_CONTENT,
        dependencies=[Depends(rate_limited(limiter, SIGN_IN_LIMIT))],
    )
    async def sign_in_admin(body: AdminSignInRequest, request: Request, response: Response) -> None:
        """Open an admin session; 401 `invalid_credentials` for a wrong login or password."""
        cookie = await access.sign_in(body.username, body.password, client_address(request))
        response.set_cookie(
            ADMIN_COOKIE, cookie, max_age=int(ADMIN_SESSION_LIFETIME.total_seconds()),
            path=ADMIN_PATH, domain=cookies.domain, secure=cookies.secure, httponly=True,
            samesite="strict",
        )  # fmt: skip

    @router.get(
        "",
        status_code=HTTPStatus.NO_CONTENT,
        dependencies=[Depends(require_admin(ports))],
    )
    async def read_admin_session() -> None:
        """204 while the admin is signed in; 401 `admin_sign_in_required` otherwise."""

    @router.delete("", status_code=HTTPStatus.NO_CONTENT)
    async def sign_out_admin(
        response: Response,
        cookie: Annotated[
            str | None, Cookie(alias=ADMIN_COOKIE, max_length=ADMIN_COOKIE_LENGTH)
        ] = None,
    ) -> None:
        """End the admin session; repeating it changes nothing."""
        await access.sign_out(cookie)
        response.delete_cookie(
            ADMIN_COOKIE, path=ADMIN_PATH, domain=cookies.domain, secure=cookies.secure,
            httponly=True, samesite="strict",
        )  # fmt: skip

    return router
