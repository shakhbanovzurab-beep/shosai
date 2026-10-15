"""Sign-in by an emailed code from the cabinet: `/v1/auth/email/*` (ADR 0048)."""

from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import Response

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.application.email_sign_in import (
    ChallengeStarted,
    EmailSignIn,
    EmailStart,
)
from shosai.features.identity.application.registration import ClientFacts
from shosai.features.identity.channels.http.cookies import CookiePolicy, set_session_cookies
from shosai.features.identity.channels.http.registration import client_facts
from shosai.features.identity.channels.http.social import COUNTRY_HEADER
from shosai.features.identity.channels.http.social_finish import SocialSession
from shosai.features.identity.domain.sessions import new_csrf_token

START_LIMIT: Final = RateLimit("identity.email_start", 5, timedelta(minutes=1), 5)
VERIFY_LIMIT: Final = RateLimit("identity.email_verify", 10, timedelta(minutes=1), 10)
RESEND_LIMIT: Final = RateLimit("identity.email_resend", 5, timedelta(minutes=1), 5)
CHALLENGE_LENGTH: Final = 2048


class EmailStartRequest(BaseModel):
    """The address a person typed on the sign-in screen."""

    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(min_length=3, max_length=254)]
    language: Annotated[str, Field(min_length=2, max_length=16)] = "en"
    next: Annotated[str, Field(max_length=256)] = ""
    captcha_token: Annotated[str | None, Field(max_length=4096)] = None


class EmailChallenge(BaseModel):
    """The sealed challenge the browser keeps, and when it may ask for another code."""

    challenge: str
    resend_after_seconds: int


class ChallengeRequest(BaseModel):
    """A challenge, for a new code."""

    model_config = ConfigDict(extra="forbid")

    challenge: Annotated[str, Field(min_length=16, max_length=CHALLENGE_LENGTH)]


class EmailVerifyRequest(BaseModel):
    """The challenge and the code from the mail."""

    model_config = ConfigDict(extra="forbid")

    challenge: Annotated[str, Field(min_length=16, max_length=CHALLENGE_LENGTH)]
    code: Annotated[str, Field(pattern=r"^\d{6}$")]


class EmailVerified(BaseModel):
    """`session` for a known person; `consent_ticket` for a new one, for the consent screen."""

    session: SocialSession | None
    consent_ticket: str | None
    next: str


def build_email_sign_in_router(
    sign_in: EmailSignIn, limiter: RateLimiter, cookies: CookiePolicy
) -> APIRouter:
    """The three routes of sign-in by code."""
    router = APIRouter(prefix="/v1/auth/email", tags=["auth"])

    @router.post(
        "/start",
        status_code=HTTPStatus.ACCEPTED,
        dependencies=[Depends(rate_limited(limiter, START_LIMIT))],
    )
    async def start(
        body: EmailStartRequest,
        client: Annotated[ClientFacts, Depends(client_facts)],
        country: Annotated[str | None, Header(alias=COUNTRY_HEADER, max_length=2)] = None,
    ) -> EmailChallenge:
        """Mail a 6-digit code; the answer is the same whether or not an account exists."""
        form = EmailStart(
            email=body.email,
            language=body.language,
            next_path=body.next,
            captcha_token=body.captcha_token,
            country=country,
        )
        return _challenge(await sign_in.start(form, client))

    @router.post(
        "/resend",
        status_code=HTTPStatus.ACCEPTED,
        dependencies=[Depends(rate_limited(limiter, RESEND_LIMIT))],
    )
    async def resend(body: ChallengeRequest) -> EmailChallenge:
        """Mail a new code: three at most, a minute apart; earlier codes stop working."""
        return _challenge(await sign_in.resend(body.challenge))

    @router.post("/verify", dependencies=[Depends(rate_limited(limiter, VERIFY_LIMIT))])
    async def verify(
        body: EmailVerifyRequest,
        response: Response,
        client: Annotated[ClientFacts, Depends(client_facts)],
    ) -> EmailVerified:
        """Sign in with the code, or get a consent ticket; five wrong codes end the challenge."""
        verified = await sign_in.verify(body.challenge, body.code, client)
        if verified.tokens is None:
            return EmailVerified(
                session=None, consent_ticket=verified.consent_ticket, next=verified.next_path
            )
        csrf_token = new_csrf_token()
        set_session_cookies(response, cookies, verified.tokens.refresh_token, csrf_token)
        session = SocialSession(
            access_token=verified.tokens.access_token,
            expires_in=verified.tokens.expires_in,
            csrf_token=csrf_token,
            next=verified.next_path,
        )
        return EmailVerified(session=session, consent_ticket=None, next=verified.next_path)

    return router


def _challenge(started: ChallengeStarted) -> EmailChallenge:
    return EmailChallenge(
        challenge=started.challenge,
        resend_after_seconds=int(started.resend_after.total_seconds()),
    )
