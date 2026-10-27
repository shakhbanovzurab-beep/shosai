"""The summary of what Leo remembers and its "Ask or update" box (memory plan §3.3, step 7).

`GET /v1/agent/memory/summary` never calls a model: the last good summary, when it was written
and whether it is stale; a stale one is rewritten in the background. `POST …/summary/refresh`
rewrites it now, ten times an hour at most. `POST …/summary/messages` answers a question about
what Leo remembers or changes it as the message asks, once per `Idempotency-Key`, each change
with its fact so the dialog can undo it (`POST /v1/agent/memory/{id}/restore`). Errors:
`memory_off` (409), `consent_required` (403), `rate_limited` (429), `memory_unavailable` (503).
"""

from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.kernel.errors import AppError
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.memory.application.box_changes import ChangeKind
from shosai.features.memory.application.box_messages import BoxMessages
from shosai.features.memory.application.summaries import Summaries, SummaryView, Written
from shosai.features.memory.channels.http.facts import MemoryFactOut, Out, Strict, fact_out
from shosai.features.memory.infrastructure.metrics import SummaryTrigger

MESSAGE_MAX: Final = 2_000
REFRESH_LIMIT: Final = RateLimit("memory.summary_refresh", 10, timedelta(hours=1), 10)
# Отказ переписать сводку сейчас — код ошибки API и его статус.
REFUSALS: Final = {
    Written.OFF: ("memory_off", HTTPStatus.CONFLICT),
    Written.NO_CONSENT: ("consent_required", HTTPStatus.FORBIDDEN),
    Written.FAILED: ("memory_unavailable", HTTPStatus.SERVICE_UNAVAILABLE),
    Written.REFUSED: ("memory_unavailable", HTTPStatus.SERVICE_UNAVAILABLE),
}


class MemorySummarySectionOut(Out):
    """A titled part of the summary."""

    title: str
    body: str


class MemorySummaryOut(Out):
    """What Leo has learned about you, in your interface language."""

    sections: list[MemorySummarySectionOut] = Field(description="Empty when nothing is known.")
    suggestions: list[str] = Field(description="Up to three questions to ask about it.")
    updated_at: datetime | None = Field(description="When it was written; null if never.")
    stale: bool = Field(description="Facts changed since; a rewrite is on its way.")


class MemoryMessageIn(Strict):
    """A question about what Leo remembers, or what to change in it."""

    message: str = Field(min_length=1, max_length=MESSAGE_MAX)


class MemoryChangeOut(Out):
    """A fact the message changed."""

    change: ChangeKind
    fact: MemoryFactOut = Field(description="The fact as it is now.")
    replaced_id: UUID | None = Field(
        description="For `updated`, the fact it replaced: restoring that one undoes the change."
    )


class MemoryMessageOut(Out):
    """The answer, the changes and the summary after them."""

    answer: str | None = Field(description="The answer to a question; null if none was asked.")
    changes: list[MemoryChangeOut]
    summary: MemorySummaryOut


def summary_out(view: SummaryView) -> MemorySummaryOut:
    """The contract's shape of the summary."""
    return MemorySummaryOut(
        sections=[
            MemorySummarySectionOut(title=section.title, body=section.body)
            for section in view.summary.sections
        ],
        suggestions=list(view.summary.suggestions),
        updated_at=view.updated_at,
        stale=view.stale,
    )


def build_summary_router(
    services: tuple[Summaries, BoxMessages], ports: PortDirectory, limiter: RateLimiter
) -> APIRouter:
    """The summary's routes; declared before `/{id}` so their paths are never read as ids."""
    summaries, box = services
    router = APIRouter(prefix="/v1/agent/memory/summary", tags=["memory"])
    signed_in = Annotated[Principal, Depends(bearer_principal(ports))]

    def person(principal: signed_in) -> str:
        return str(principal.user_id)

    @router.get("")
    async def get_memory_summary(principal: signed_in) -> MemorySummaryOut:
        """What Leo has learned about you; a stale summary is rewritten in the background."""
        return summary_out(await summaries.view(principal.scope()))

    @router.post("/refresh", dependencies=[Depends(rate_limited(limiter, REFRESH_LIMIT, person))])
    async def refresh_memory_summary(principal: signed_in) -> MemorySummaryOut:
        """Rewrite the summary now."""
        written = await summaries.write(principal.scope(), SummaryTrigger.REFRESH)
        if written in REFUSALS:
            code, status = REFUSALS[written]
            raise AppError(code, status)
        return summary_out(await summaries.view(principal.scope(), rewrite=False))

    @router.post("/messages")
    async def post_memory_message(
        principal: signed_in, body: MemoryMessageIn, key: IdempotencyKeyHeader
    ) -> MemoryMessageOut:
        """Ask about what Leo remembers, or tell it what to remember, correct or forget."""
        result = await box.handle(principal, body.message, key)
        return MemoryMessageOut(
            answer=result.answer,
            changes=[
                MemoryChangeOut(change=kind, fact=fact_out(view), replaced_id=replaced)
                for kind, view, replaced in result.changes
            ],
            summary=summary_out(result.summary),
        )

    return router
