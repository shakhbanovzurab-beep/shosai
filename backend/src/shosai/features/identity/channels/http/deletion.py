"""Deleting the account: `POST /v1/me/deletion` (class web, ID-D5).

The answer is 202 with the time of the final erasure; every session has ended by then, so
the cabinet's cookies are cleared in the same answer. Signing in before that time cancels
the deletion.
"""

from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Annotated, Final

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import Response

from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.application.deletion import Deletions
from shosai.features.identity.channels.http.cookies import CookiePolicy, clear_session_cookies
from shosai.features.identity.contracts import Principal, bearer_principal

DELETION_LIMIT: Final = RateLimit("identity.deletion", 5, timedelta(minutes=1), 5)


class DeletionRequest(BaseModel):
    """The account's address, typed again to confirm."""

    model_config = ConfigDict(extra="forbid")

    confirm_email: Annotated[str, Field(min_length=3, max_length=254)]


class DeletionScheduled(BaseModel):
    """When the hidden account is erased unless the person signs in before."""

    erase_at: datetime


def build_deletion_router(
    deletions: Deletions, ports: PortDirectory, limiter: RateLimiter, cookies: CookiePolicy
) -> APIRouter:
    """The deletion route of the signed-in person."""
    router = APIRouter(prefix="/v1/me", tags=["me"])
    signed_in = bearer_principal(ports)

    @router.post(
        "/deletion",
        status_code=HTTPStatus.ACCEPTED,
        dependencies=[Depends(rate_limited(limiter, DELETION_LIMIT))],
    )
    async def request_deletion(
        body: DeletionRequest,
        response: Response,
        principal: Annotated[Principal, Depends(signed_in)],
    ) -> DeletionScheduled:
        """Hide the account and erase it in 7 days; needs a sign-in in the last 15 minutes.

        400 `confirmation_mismatch` when the address differs from the account's; 403
        `reauthentication_required` when the session is older.
        """
        erase_at = await deletions.schedule(principal, body.confirm_email)
        clear_session_cookies(response, cookies)
        return DeletionScheduled(erase_at=erase_at)

    return router
