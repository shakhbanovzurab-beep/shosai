"""Leo's turns over Server-Sent Events (agent plan §3.3, ADR 0032, step 5a).

`POST /v1/agent/threads/{id}/turns` admits a turn and streams its run; the same
`Idempotency-Key` again streams the same run from its first event. Every refusal comes before
the stream, as the platform's envelope: `question_invalid`, `thread_not_found`,
`consent_required` (403), `token_limit` (402, `params.limit`), `thread_busy` (409),
`rate_limited`, `too_many_runs`, `agent_busy` (429 with `Retry-After`), `agent_unavailable`,
`entitlements_unavailable` (503), `idempotency_key_reused`, `validation_error`. Each event
has the run's next number as its id, and a comment every 15 s keeps the connection open.
`GET /v1/agent/runs/{id}/events` resumes after `Last-Event-ID` (410 `run_events_gone` after
the log's hour); `POST /v1/agent/runs/{id}/cancel` asks the run to stop (202).
"""

from collections.abc import AsyncIterable
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import Field

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.run_streams import RunStreams
from shosai.features.agent.application.turn_start import TurnRequest, TurnStarter
from shosai.features.agent.channels.http.shapes import Strict
from shosai.features.agent.domain.stream import StreamEvent
from shosai.features.agent.domain.threads import QUESTION_MAX
from shosai.features.identity.contracts import Principal, bearer_principal

LOCALE_MAX = 16
# Сырой текст длиннее вопроса на поля по краям: обрезанный пробелами вопрос проверяет домен.
TEXT_MAX = QUESTION_MAX * 2


class TurnBody(Strict):
    """A question for Leo."""

    text: str = Field(max_length=TEXT_MAX, description="The question, 1 to 4 000 characters.")
    locale: str | None = Field(
        default=None,
        max_length=LOCALE_MAX,
        description="The interface's language; Leo answers in it unless Settings > Leo names one.",
    )
    supersede: bool = Field(
        default=False, description="Stop the answer still being written in this thread first."
    )


def server_event(event: StreamEvent) -> ServerSentEvent:
    """One event of the run as SSE: its kind, its number and its data."""
    return ServerSentEvent(data=dict(event.data), event=event.kind.value, id=str(event.seq))


def build_turns_router(services: tuple[TurnStarter, RunStreams], ports: PortDirectory) -> APIRouter:
    """The routes of turns and runs."""
    starter, streams = services
    router = APIRouter(prefix="/v1/agent", tags=["agent"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    async def admitted_run(
        principal: person, thread_id: UUID, body: TurnBody, idempotency_key: IdempotencyKeyHeader
    ) -> UUID:
        request = TurnRequest(body.text, body.locale, body.supersede)
        return await starter.start(principal, thread_id, request, idempotency_key)

    async def resumable_run(principal: person, run_id: UUID) -> UUID:
        return (await streams.resumable(principal, run_id)).run_id

    @router.post("/threads/{thread_id}/turns", response_class=EventSourceResponse)
    async def take_turn(
        principal: person, run: Annotated[UUID, Depends(admitted_run)]
    ) -> AsyncIterable[ServerSentEvent]:
        """Ask Leo; the answer streams as the run's events."""
        async for event in streams.events(principal, run, 0):
            yield server_event(event)

    @router.get("/runs/{run_id}/events", response_class=EventSourceResponse)
    async def resume_run(
        principal: person,
        run: Annotated[UUID, Depends(resumable_run)],
        last_event_id: Annotated[
            int, Header(alias="Last-Event-ID", ge=0, description="The last event's id seen.")
        ] = 0,
    ) -> AsyncIterable[ServerSentEvent]:
        """The run's events after the last one the client saw."""
        async for event in streams.events(principal, run, last_event_id):
            yield server_event(event)

    @router.post("/runs/{run_id}/cancel", status_code=HTTPStatus.ACCEPTED)
    async def cancel_run(principal: person, run_id: UUID) -> Response:
        """Ask the run to stop; the answer keeps its text so far."""
        await streams.stop(principal, run_id)
        return Response(status_code=HTTPStatus.ACCEPTED)

    return router
