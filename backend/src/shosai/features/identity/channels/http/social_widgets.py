"""Sign-in through providers' widgets in the cabinet: Yandex and Google tokens, VK ID OneTap.

Yandex's and Google's widgets hand the browser a token the server checks with the provider.
VK ID OneTap works like the redirect flow without leaving the page: `widget-start` opens the
flow and keeps the PKCE verifier on the server, and `widget-code` takes the code, the state
and the device id the widget handed back. All three answer with the tickets of
`social_finish`: a session ticket for a known person, a consent ticket for a new one.
"""

from collections.abc import Awaitable
from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.kernel.errors import AppError
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.application.social import (
    Outcome,
    SocialRefusedError,
    SocialSignIn,
)
from shosai.features.identity.channels.http.social import COUNTRY_HEADER
from shosai.features.identity.domain.social import Provider, visible_providers
from shosai.features.identity.infrastructure.social.base import SocialProviderFailedError
from shosai.features.identity.infrastructure.social.flows import SocialStateUnavailableError

WIDGET_LIMIT: Final = RateLimit("identity.social_widget", 20, timedelta(minutes=1), 20)


class WidgetTokenRequest(BaseModel):
    """A token the provider's widget handed the browser."""

    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, Field(min_length=1, max_length=4096)]
    next: Annotated[str | None, Field(max_length=256)] = None
    language: Annotated[str, Field(min_length=2, max_length=16)] = "en"


class WidgetStartRequest(BaseModel):
    """Where to return after sign-in through a code widget, and the interface language."""

    model_config = ConfigDict(extra="forbid")

    next: Annotated[str | None, Field(max_length=256)] = None
    language: Annotated[str, Field(min_length=2, max_length=16)] = "en"


class WidgetStart(BaseModel):
    """What VK ID OneTap is configured with: its `state`, `codeChallenge` and `redirectUrl`."""

    state: str
    code_challenge: str
    redirect_url: str


class WidgetCodeRequest(BaseModel):
    """What the code widget handed the browser after the person allowed sign-in."""

    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, Field(min_length=1, max_length=1024)]
    state: Annotated[str, Field(min_length=1, max_length=256)]
    device_id: Annotated[str, Field(min_length=1, max_length=256)]


class SocialTickets(BaseModel):
    """`social` for a known person (then `complete`), `social_consent` for a new one."""

    social: str | None
    social_consent: str | None
    next: str


async def _tickets(resolving: Awaitable[Outcome]) -> SocialTickets:
    """The tickets of a resolved person, or the refusal as the API's error."""
    try:
        outcome = await resolving
    except SocialRefusedError as refused:
        raise AppError(refused.code, HTTPStatus.UNAUTHORIZED) from refused
    except SocialProviderFailedError as failed:
        raise AppError("social_provider_failed", HTTPStatus.UNAUTHORIZED) from failed
    except SocialStateUnavailableError as down:
        raise AppError("social_unavailable", HTTPStatus.SERVICE_UNAVAILABLE) from down
    return SocialTickets(
        social=outcome.session_ticket, social_consent=outcome.consent_ticket, next=outcome.next_path
    )


def build_social_widgets_router(social: SocialSignIn, limiter: RateLimiter) -> APIRouter:
    """The routes of providers' widgets."""
    router = APIRouter(prefix="/v1/auth/social", tags=["auth"])
    limited = [Depends(rate_limited(limiter, WIDGET_LIMIT))]

    @router.post("/{provider}/widget-token", dependencies=limited)
    async def widget_token(provider: Provider, body: WidgetTokenRequest) -> SocialTickets:
        """Resolve the person behind a Yandex or Google widget token."""
        return await _tickets(social.widget(provider, body.token, body.next, body.language))

    @router.post("/{provider}/widget-start", dependencies=limited)
    async def widget_start(
        provider: Provider,
        body: WidgetStartRequest,
        country: Annotated[str | None, Header(alias=COUNTRY_HEADER, max_length=2)] = None,
    ) -> WidgetStart:
        """Open a flow for VK ID OneTap; the PKCE verifier stays on the server."""
        if provider not in visible_providers(country, body.language):
            raise AppError("social_provider_disabled", HTTPStatus.CONFLICT)
        try:
            flow = await social.widget_flow(provider, body.next, body.language)
        except SocialRefusedError as refused:
            raise AppError(refused.code, HTTPStatus.CONFLICT) from refused
        except SocialStateUnavailableError as down:
            raise AppError("social_unavailable", HTTPStatus.SERVICE_UNAVAILABLE) from down
        return WidgetStart(
            state=flow.state, code_challenge=flow.code_challenge, redirect_url=flow.redirect_uri
        )

    @router.post("/{provider}/widget-code", dependencies=limited)
    async def widget_code(provider: Provider, body: WidgetCodeRequest) -> SocialTickets:
        """Resolve the person behind the code VK ID OneTap handed the browser."""
        return await _tickets(social.callback(provider, body.code, body.state, body.device_id))

    return router
