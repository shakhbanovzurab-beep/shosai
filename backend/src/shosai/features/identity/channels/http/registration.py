"""Registration routes of the cabinet: `/v1/auth/register*` (identity plan §3.4).

Class `web`: no shipped client calls them, so they follow v2's contract — snake_case,
the ADR 0008 envelope, codes the cabinet translates. A confirmed registration is signed
in at once: `verify` answers with the session and sets its cookies, as sign-in does.
"""

from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request
from starlette.responses import Response

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.web.rate_limit import client_address, rate_limited
from shosai.features.identity.application.registration import (
    ClientFacts,
    Registration,
    RegistrationForm,
    RegistrationStarted,
)
from shosai.features.identity.application.verification import Verification
from shosai.features.identity.channels.http.cookies import CookiePolicy, set_session_cookies
from shosai.features.identity.domain.registration import RegistrationConsents
from shosai.features.identity.domain.sessions import new_csrf_token

REGISTER_LIMIT: Final = RateLimit("identity.register", 5, timedelta(minutes=1), 5)
VERIFY_LIMIT: Final = RateLimit("identity.register_verify", 10, timedelta(minutes=1), 10)
RESEND_LIMIT: Final = RateLimit("identity.register_resend", 5, timedelta(minutes=1), 5)
MAX_USER_AGENT: Final = 512


class Consents(BaseModel):
    """The consents of the registration form; personal data is required."""

    model_config = ConfigDict(extra="forbid")

    personal_data: bool
    # Обязательно для дома РФ (nfr-14): без него ни одна функция Shosai не работает.
    cross_border: bool = False
    marketing: bool = False


class RegistrationRequest(BaseModel):
    """A new account: the address, a password, the name and where the person lives."""

    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=1, max_length=256)]
    full_name: Annotated[str, Field(min_length=1, max_length=80, pattern=r"\S")]
    country: Annotated[str, Field(pattern=r"^[A-Z]{2}$", description="ISO 3166-1 alpha-2.")]
    language: Annotated[str, Field(min_length=2, max_length=16)]
    consents: Consents
    captcha_token: Annotated[str | None, Field(max_length=4096)] = None


class RegistrationStartedResponse(BaseModel):
    """The id to confirm the code with, and when another code may be asked for."""

    registration_id: UUID
    resend_after_seconds: int


class VerifyRequest(BaseModel):
    """The code mailed to the address, with the id of the registration it belongs to."""

    model_config = ConfigDict(extra="forbid")

    registration_id: UUID
    code: Annotated[str, Field(pattern=r"^[0-9]{6}$")]


class ResendRequest(BaseModel):
    """The registration to mail a new code for."""

    model_config = ConfigDict(extra="forbid")

    registration_id: UUID


class AccountCreatedResponse(BaseModel):
    """The account the confirmed registration created, signed in as at sign-in."""

    user_id: UUID
    access_token: str
    expires_in: int
    token_type: str = Field(default="Bearer")
    csrf_token: str


def client_facts(
    request: Request, user_agent: Annotated[str | None, Header()] = None
) -> ClientFacts:
    """The client's address and user agent, for the consent journal and the captcha."""
    return ClientFacts(client_address(request), (user_agent or "")[:MAX_USER_AGENT] or None)


def build_registration_router(
    registration: Registration,
    verification: Verification,
    limiter: RateLimiter,
    cookies: CookiePolicy,
) -> APIRouter:
    """The three registration routes."""
    router = APIRouter(prefix="/v1/auth/register", tags=["auth"])

    @router.post(
        "",
        status_code=HTTPStatus.ACCEPTED,
        dependencies=[Depends(rate_limited(limiter, REGISTER_LIMIT))],
    )
    async def register(
        body: RegistrationRequest, client: Annotated[ClientFacts, Depends(client_facts)]
    ) -> RegistrationStartedResponse:
        """Mail a 6-digit code to the address; the answer is the same for a taken address."""
        form = RegistrationForm(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            country=body.country,
            language=body.language,
            consents=RegistrationConsents(
                personal_data=body.consents.personal_data,
                cross_border=body.consents.cross_border,
                marketing=body.consents.marketing,
            ),
            captcha_token=body.captcha_token,
        )
        return _started(await registration.start(form, client))

    @router.post(
        "/verify",
        status_code=HTTPStatus.CREATED,
        dependencies=[Depends(rate_limited(limiter, VERIFY_LIMIT))],
    )
    async def verify(
        body: VerifyRequest,
        response: Response,
        client: Annotated[ClientFacts, Depends(client_facts)],
    ) -> AccountCreatedResponse:
        """Create the account and sign it in when the code is right; five wrong codes end
        the registration."""
        verified = await verification.confirm(body.registration_id, body.code, client)
        csrf_token = new_csrf_token()
        set_session_cookies(response, cookies, verified.tokens.refresh_token, csrf_token)
        return AccountCreatedResponse(
            user_id=verified.user_id,
            access_token=verified.tokens.access_token,
            expires_in=verified.tokens.expires_in,
            csrf_token=csrf_token,
        )

    @router.post(
        "/resend",
        status_code=HTTPStatus.ACCEPTED,
        dependencies=[Depends(rate_limited(limiter, RESEND_LIMIT))],
    )
    async def resend(body: ResendRequest) -> RegistrationStartedResponse:
        """Mail a new code: three at most, a minute apart; earlier codes stop working."""
        return _started(await registration.resend(body.registration_id))

    return router


def _started(started: RegistrationStarted) -> RegistrationStartedResponse:
    return RegistrationStartedResponse(
        registration_id=started.registration_id,
        resend_after_seconds=int(started.resend_after.total_seconds()),
    )
