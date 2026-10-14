"""Password routes of the cabinet: forgot, reset by link, change (identity plan §3.4)."""

from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import Response

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.application.passwords import Passwords
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.channels.http.cookies import CookiePolicy, set_session_cookies
from shosai.features.identity.channels.http.native_models import TokenResponse
from shosai.features.identity.channels.http.registration import client_facts
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.identity.domain.sessions import new_csrf_token

FORGOT_LIMIT: Final = RateLimit("identity.password_forgot", 5, timedelta(minutes=1), 5)
RESET_LIMIT: Final = RateLimit("identity.password_reset", 10, timedelta(minutes=1), 10)
CHANGE_LIMIT: Final = RateLimit("identity.password_change", 5, timedelta(minutes=1), 5)


class ForgotRequest(BaseModel):
    """The address to mail a reset link to; the captcha is always shown here."""

    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(min_length=3, max_length=254)]
    captcha_token: Annotated[str | None, Field(max_length=4096)] = None


class ResetRequest(BaseModel):
    """The token of the link and the new password."""

    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, Field(min_length=8, max_length=128)]
    password: Annotated[str, Field(min_length=1, max_length=256)]


class ChangeRequest(BaseModel):
    """The current password (none for an account without one) and the new one."""

    model_config = ConfigDict(extra="forbid")

    current_password: Annotated[str | None, Field(max_length=256)] = None
    new_password: Annotated[str, Field(min_length=1, max_length=256)]


def build_password_router(
    passwords: Passwords, ports: PortDirectory, limiter: RateLimiter, cookies: CookiePolicy
) -> APIRouter:
    """The three password routes."""
    router = APIRouter(tags=["auth"])
    signed_in = bearer_principal(ports)

    @router.post(
        "/v1/auth/password/forgot",
        status_code=HTTPStatus.ACCEPTED,
        dependencies=[Depends(rate_limited(limiter, FORGOT_LIMIT))],
    )
    async def forgot(
        body: ForgotRequest, client: Annotated[ClientFacts, Depends(client_facts)]
    ) -> None:
        """Mail a reset link if an active account has the address; the answer is the same."""
        await passwords.forgot(body.email, body.captcha_token, client)

    @router.post(
        "/v1/auth/password/reset",
        status_code=HTTPStatus.NO_CONTENT,
        dependencies=[Depends(rate_limited(limiter, RESET_LIMIT))],
    )
    async def reset(body: ResetRequest) -> Response:
        """Set the new password by the link, once; every session of the account ends."""
        await passwords.reset(body.token, body.password)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post("/v1/me/password", dependencies=[Depends(rate_limited(limiter, CHANGE_LIMIT))])
    async def change(
        body: ChangeRequest,
        response: Response,
        principal: Annotated[Principal, Depends(signed_in)],
        client: Annotated[ClientFacts, Depends(client_facts)],
    ) -> TokenResponse:
        """Change the password; other sessions end, this one continues with new tokens."""
        tokens = await passwords.change(principal, body.current_password, body.new_password, client)
        csrf_token = new_csrf_token()
        set_session_cookies(response, cookies, tokens.refresh_token, csrf_token)
        return TokenResponse(
            access_token=tokens.access_token, expires_in=tokens.expires_in, csrf_token=csrf_token
        )

    return router
