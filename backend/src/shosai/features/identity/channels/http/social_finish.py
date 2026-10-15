"""Finishing social sign-in from the cabinet: a widget's token, a ticket, the consent screen."""

from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import Response

from shosai.core.kernel.errors import AppError
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.application.sessions import IssuedTokens
from shosai.features.identity.application.social import SocialRefusedError, SocialSignIn
from shosai.features.identity.application.social_accounts import (
    SocialAccounts,
    SocialRegistration,
)
from shosai.features.identity.channels.http.cookies import CookiePolicy, set_session_cookies
from shosai.features.identity.channels.http.registration import Consents, client_facts
from shosai.features.identity.domain.registration import RegistrationConsents
from shosai.features.identity.domain.sessions import new_csrf_token
from shosai.features.identity.domain.social import Provider
from shosai.features.identity.infrastructure.social.base import SocialProviderFailedError

FINISH_LIMIT: Final = RateLimit("identity.social_finish", 20, timedelta(minutes=1), 20)


class WidgetTokenRequest(BaseModel):
    """A token the provider's widget handed the browser."""

    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, Field(min_length=1, max_length=4096)]
    next: Annotated[str | None, Field(max_length=256)] = None
    language: Annotated[str, Field(min_length=2, max_length=16)] = "en"


class SocialTickets(BaseModel):
    """`social` for a known person (then `complete`), `social_consent` for a new one."""

    social: str | None
    social_consent: str | None
    next: str


class TicketRequest(BaseModel):
    """A session ticket from the redirect or the widget."""

    model_config = ConfigDict(extra="forbid")

    ticket: Annotated[str, Field(min_length=16, max_length=128)]


class SocialRegisterRequest(BaseModel):
    """The consent screen: the ticket, the country, the language and the consents."""

    model_config = ConfigDict(extra="forbid")

    ticket: Annotated[str, Field(min_length=16, max_length=4096)]
    country: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    language: Annotated[str, Field(min_length=2, max_length=16)]
    consents: Consents


class SocialSession(BaseModel):
    """The session the cabinet keeps, and where to go next."""

    access_token: str
    expires_in: int
    token_type: str = Field(default="Bearer")
    csrf_token: str
    next: str


def build_social_finish_router(
    social: SocialSignIn, accounts: SocialAccounts, limiter: RateLimiter, cookies: CookiePolicy
) -> APIRouter:
    """The cabinet's side of social sign-in."""
    router = APIRouter(prefix="/v1/auth/social", tags=["auth"])
    limited = [Depends(rate_limited(limiter, FINISH_LIMIT))]

    def session(response: Response, tokens: IssuedTokens, next_path: str) -> SocialSession:
        csrf_token = new_csrf_token()
        set_session_cookies(response, cookies, tokens.refresh_token, csrf_token)
        return SocialSession(
            access_token=tokens.access_token, expires_in=tokens.expires_in,
            csrf_token=csrf_token, next=next_path,
        )  # fmt: skip

    @router.post("/{provider}/widget-token", dependencies=limited)
    async def widget_token(provider: Provider, body: WidgetTokenRequest) -> SocialTickets:
        """Resolve the person behind a Yandex or Google widget token."""
        try:
            outcome = await social.widget(provider, body.token, body.next, body.language)
        except SocialRefusedError as refused:
            raise AppError(refused.code, HTTPStatus.UNAUTHORIZED) from refused
        except SocialProviderFailedError as failed:
            raise AppError("social_provider_failed", HTTPStatus.UNAUTHORIZED) from failed
        return SocialTickets(
            social=outcome.session_ticket,
            social_consent=outcome.consent_ticket,
            next=outcome.next_path,
        )

    @router.post("/complete", dependencies=limited)
    async def complete(
        body: TicketRequest,
        response: Response,
        client: Annotated[ClientFacts, Depends(client_facts)],
    ) -> SocialSession:
        """The session of a known person; the ticket works once, for two minutes."""
        tokens, next_path = await accounts.complete(body.ticket, client)
        return session(response, tokens, next_path)

    @router.post("/register", dependencies=limited)
    async def register(
        body: SocialRegisterRequest,
        response: Response,
        client: Annotated[ClientFacts, Depends(client_facts)],
    ) -> SocialSession:
        """A new account for the person a provider or a code introduced, after their consent."""
        form = SocialRegistration(
            ticket=body.ticket,
            country=body.country,
            language=body.language,
            consents=RegistrationConsents(
                personal_data=body.consents.personal_data,
                cross_border=body.consents.cross_border,
                marketing=body.consents.marketing,
            ),
        )
        tokens, next_path = await accounts.register(form, client)
        return session(response, tokens, next_path)

    return router
