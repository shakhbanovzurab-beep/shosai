"""Desktop sign-in routes: the code for the app (web) and its exchange and refresh (native).

`/v1/auth/desktop/exchange` and `/desktop/refresh` are the routes the shipped macOS and
Windows 1.4.5 clients call; their shapes and `detail` strings are the draft's (D1 gate).
The exchange also reads the `code_verifier` macOS already sends; a client that sends none
still works for a code issued without a challenge.
"""

from datetime import timedelta
from typing import Annotated, Final

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.application.desktop import DesktopSignIn
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.application.sessions import IssuedTokens
from shosai.features.identity.channels.http.registration import client_facts
from shosai.features.identity.contracts import Principal, bearer_principal

CODE_LIMIT: Final = RateLimit("identity.desktop_code", 10, timedelta(minutes=1), 10)
EXCHANGE_LIMIT: Final = RateLimit("identity.desktop_exchange", 10, timedelta(minutes=1), 10)
REFRESH_LIMIT: Final = RateLimit("identity.desktop_refresh", 30, timedelta(minutes=1), 30)


class DesktopCodeRequest(BaseModel):
    """The app's PKCE challenge, passed on by the connect page when the app sent one."""

    code_challenge: Annotated[str | None, Field(max_length=128)] = None
    code_challenge_method: Annotated[str | None, Field(max_length=8)] = None


class DesktopCodeResponse(BaseModel):
    """The one-time code for `shosai://auth` and its lifetime in seconds."""

    code: str
    expires_in: int


class DesktopExchangeRequest(BaseModel):
    """The code from `shosai://auth`, and the PKCE verifier if the app sent a challenge."""

    code: Annotated[str, Field(min_length=8, max_length=256)]
    code_verifier: Annotated[str | None, Field(max_length=128)] = None


class DesktopRefreshRequest(BaseModel):
    """The app's current refresh token."""

    refresh_token: Annotated[str, Field(min_length=8, max_length=4096)]


class DesktopTokenResponse(BaseModel):
    """The app's tokens: it keeps the refresh token in the system's key store."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = Field(default="Bearer")


def desktop_tokens(tokens: IssuedTokens) -> DesktopTokenResponse:
    """The draft's desktop token answer."""
    return DesktopTokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


def build_desktop_router(
    desktop: DesktopSignIn, ports: PortDirectory, limiter: RateLimiter
) -> APIRouter:
    """The three desktop sign-in routes."""
    router = APIRouter(prefix="/v1/auth/desktop", tags=["auth"])
    signed_in = bearer_principal(ports)

    @router.post("/code", dependencies=[Depends(rate_limited(limiter, CODE_LIMIT))])
    async def issue_code(
        principal: Annotated[Principal, Depends(signed_in)],
        body: DesktopCodeRequest | None = None,
    ) -> DesktopCodeResponse:
        """A one-time code for the desktop app, after the person confirmed on the page."""
        request = body or DesktopCodeRequest()
        issued = await desktop.issue(
            principal, request.code_challenge, request.code_challenge_method
        )
        return DesktopCodeResponse(code=issued.code, expires_in=issued.expires_in)

    @router.post("/exchange", dependencies=[Depends(rate_limited(limiter, EXCHANGE_LIMIT))])
    async def exchange(
        body: DesktopExchangeRequest, client: Annotated[ClientFacts, Depends(client_facts)]
    ) -> DesktopTokenResponse:
        """The app's own session for the code; the code works once, for 120 seconds."""
        return desktop_tokens(await desktop.exchange(body.code, body.code_verifier, client))

    @router.post("/refresh", dependencies=[Depends(rate_limited(limiter, REFRESH_LIMIT))])
    async def refresh(body: DesktopRefreshRequest) -> DesktopTokenResponse:
        """Rotate the app's session; a replayed old token ends it."""
        return desktop_tokens(await desktop.refresh(body.refresh_token))

    return router
