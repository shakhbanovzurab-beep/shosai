"""The native sign-in routes: `/v1/auth/login`, `/refresh`, `/logout`, `/me` (class N).

Their shapes and `detail` strings are the draft's; the D1 gate holds the shapes. Headers
the clients send (`X-Client-Kind`, `X-CSRF-Token`) and the cookies are read from the
request rather than declared, so the contract shows no parameter the draft did not have.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, Final

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.application import native_errors
from shosai.features.identity.application.native_me import NativeMe
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.application.sessions import IssuedTokens, Sessions
from shosai.features.identity.application.sign_in import SignIn, SignInAttempt
from shosai.features.identity.channels.http.cookies import (
    CLIENT_KIND_HEADER,
    CSRF_COOKIE,
    CSRF_HEADER,
    REFRESH_COOKIE,
    CookiePolicy,
    clear_session_cookies,
    set_session_cookies,
)
from shosai.features.identity.channels.http.native_models import (
    LoginRequest,
    TokenResponse,
    UserMeResponse,
)
from shosai.features.identity.channels.http.registration import client_facts
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.identity.domain.sessions import ClientKind, csrf_matches, new_csrf_token

LOGIN_LIMIT: Final = RateLimit("identity.sign_in", 5, timedelta(minutes=1), 5)


class LogoutRequest(BaseModel):
    """The refresh token of a client that keeps it outside the cookie jar (optional)."""

    refresh_token: str | None = None


def token_response(tokens: IssuedTokens, csrf_token: str | None) -> TokenResponse:
    """The draft's token answer."""
    return TokenResponse(
        access_token=tokens.access_token, expires_in=tokens.expires_in, csrf_token=csrf_token
    )


@dataclass(frozen=True, slots=True)
class SessionRoutes:
    """What the sign-in routes work with."""

    sign_in: SignIn
    sessions: Sessions
    me: NativeMe
    ports: PortDirectory
    limiter: RateLimiter
    cookies: CookiePolicy


def build_session_router(routes: SessionRoutes) -> APIRouter:
    """The four native routes of sign-in."""
    router = APIRouter(prefix="/v1/auth", tags=["auth"])
    signed_in = bearer_principal(routes.ports)
    sign_in, sessions, me, cookies = routes.sign_in, routes.sessions, routes.me, routes.cookies
    limiter = routes.limiter

    @router.post("/login", dependencies=[Depends(rate_limited(limiter, LOGIN_LIMIT))])
    async def login(
        body: LoginRequest,
        request: Request,
        response: Response,
        client: Annotated[ClientFacts, Depends(client_facts)],
    ) -> TokenResponse:
        """Sign in with the address and password; set the refresh and CSRF cookies."""
        desktop = request.headers.get(CLIENT_KIND_HEADER, "").lower() == "desktop"
        attempt = SignInAttempt(
            email=body.email,
            password=body.password,
            captcha_token=body.captcha_token,
            kind=ClientKind.DESKTOP if desktop else ClientKind.WEB,
            client=client,
        )
        tokens = await sign_in.sign_in(attempt)
        csrf_token = new_csrf_token()
        set_session_cookies(response, cookies, tokens.refresh_token, csrf_token)
        return token_response(tokens, csrf_token)

    @router.post("/refresh")
    async def refresh(request: Request, response: Response) -> TokenResponse:
        """Rotate the session of the refresh cookie; the CSRF header repeats its cookie."""
        refresh_token = request.cookies.get(REFRESH_COOKIE)
        if not refresh_token:
            raise native_errors.unauthorized("refresh_missing")
        csrf_token = request.cookies.get(CSRF_COOKIE)
        if not csrf_matches(csrf_token, request.headers.get(CSRF_HEADER)):
            raise native_errors.csrf_mismatch()
        tokens = await sessions.refresh(refresh_token)
        set_session_cookies(response, cookies, tokens.refresh_token, str(csrf_token))
        return token_response(tokens, csrf_token)

    @router.post("/logout")
    async def logout(
        request: Request, response: Response, body: LogoutRequest | None = None
    ) -> dict[str, bool]:
        """End the session of the cookie, or of a refresh token in the body; always ok."""
        refresh_token = request.cookies.get(REFRESH_COOKIE) or (body and body.refresh_token)
        if refresh_token:
            await sessions.revoke(refresh_token, "logout")
        clear_session_cookies(response, cookies)
        return {"ok": True}

    @router.get("/me")
    async def read_me(principal: Annotated[Principal, Depends(signed_in)]) -> UserMeResponse:
        """The signed-in person with their plan, minutes and switches."""
        return UserMeResponse.model_validate(await me.fields(principal))

    return router
