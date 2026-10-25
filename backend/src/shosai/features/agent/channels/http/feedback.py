"""A person's rating of Leo's answer: `PUT` and `DELETE /v1/agent/messages/{id}/feedback`
(ADR 0068 AG-D13; agent step 11a).

`PUT {rating: useful | not_useful}` answers `{rating, shared}` — `shared` says whether the turn
was kept as an evaluation case: only with the person's "Help improve the models" consent, and
never for an answer built on a workspace's data. The same rating again is answered as it
stands. `DELETE` takes the rating back, and its case with it, answering 204 whether or not
there was one. Errors use the platform's envelope: `message_not_found` (404) for a question, a
note, another person's answer or a thread the person no longer sees.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import Field

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.feedback import Feedback
from shosai.features.agent.channels.http.shapes import Out, Strict
from shosai.features.agent.domain.feedback import Rating
from shosai.features.identity.contracts import Principal, bearer_principal


class FeedbackBody(Strict):
    """What the person said about the answer."""

    rating: Rating


class FeedbackOut(Out):
    """The rating as kept."""

    rating: Rating
    shared: bool = Field(description="Whether the turn was kept as an evaluation case.")


def build_feedback_router(feedback: Feedback, ports: PortDirectory) -> APIRouter:
    """The routes of a rating under an answer."""
    router = APIRouter(prefix="/v1/agent/messages", tags=["agent"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.put("/{message_id}/feedback")
    async def rate_answer(principal: person, message_id: UUID, body: FeedbackBody) -> FeedbackOut:
        """Rate the answer; the same rating again changes nothing."""
        kept = await feedback.rate(principal, message_id, body.rating)
        return FeedbackOut(rating=kept.rating, shared=kept.shared)

    @router.delete("/{message_id}/feedback", status_code=HTTPStatus.NO_CONTENT)
    async def remove_rating(principal: person, message_id: UUID) -> Response:
        """Take the rating back, and its evaluation case with it."""
        await feedback.remove(principal, message_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
