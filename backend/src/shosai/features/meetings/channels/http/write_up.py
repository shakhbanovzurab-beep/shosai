"""The rewrite of a meeting's write-up: `POST /v1/meetings/{id}/write-up` (plan §3.4 flow 6).

The body names a shipped template's code or the id of the person's own template; the
answer is 202 with the run that rewrites the notes, whose progress `GET /v1/me/runs/{id}`
shows. Ten requests a minute per person. Errors: `meeting_not_found`, `template_not_found`,
`notes_not_ready`, `idempotency_key_reused`, `rate_limited`.
"""

from datetime import timedelta
from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.write_up_rewrites import (
    RewriteAccepted,
    RewriteRequest,
    WriteUpRewrites,
)

REWRITE_LIMIT: Final = RateLimit("meetings.write_up_rewrite", 10, timedelta(minutes=1), 10)


class RewriteIn(BaseModel):
    """Which template the write-up is rewritten by."""

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(
        min_length=1,
        max_length=128,
        description="A shipped template's code, such as `oneOnOne`, or the id of your own.",
    )


def build_write_up_router(
    rewrites: WriteUpRewrites, ports: PortDirectory, limiter: RateLimiter
) -> APIRouter:
    """The rewrite of a meeting's write-up."""
    router = APIRouter(prefix="/v1/meetings", tags=["meetings"])
    signed_in = bearer_principal(ports)

    async def person(principal: Annotated[Principal, Depends(signed_in)]) -> str:
        return str(principal.user_id)

    @router.post(
        "/{meeting_id}/write-up",
        status_code=HTTPStatus.ACCEPTED,
        dependencies=[Depends(rate_limited(limiter, REWRITE_LIMIT, person))],
    )
    async def rewrite_write_up(
        principal: Annotated[Principal, Depends(signed_in)],
        meeting_id: UUID,
        body: RewriteIn,
        idempotency_key: IdempotencyKeyHeader,
    ) -> RewriteAccepted:
        """Rewrite the meeting's write-up by a template, keeping its findings."""
        request = RewriteRequest(meeting_id=meeting_id, template_id=body.template_id)
        run_id = await rewrites.rewrite(principal, request, idempotency_key)
        return RewriteAccepted(run_id=run_id)

    return router
