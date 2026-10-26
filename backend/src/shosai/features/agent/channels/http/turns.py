"""Leo's turns over Server-Sent Events (agent plan §3.3, ADR 0032, step 5a).

`POST /v1/agent/threads/{id}/turns` admits a turn and streams its run; the same
`Idempotency-Key` again streams the same run from its first event. Every refusal comes before
the stream, as the platform's envelope: `question_invalid`, `thread_not_found`,
`consent_required` (403), `token_limit` (402, `params.limit`), `thread_busy` (409),
`rate_limited`, `too_many_runs`, `agent_busy` (429 with `Retry-After`), `agent_unavailable`,
`entitlements_unavailable` (503), `not_last_question` (409, a regenerate or an edit of any
question but the thread's last), `idempotency_key_reused`, `validation_error`. Each event
has the run's next number as its id, and a comment every 15 s keeps the connection open.
`GET /v1/agent/runs/{id}/events` resumes after `Last-Event-ID` (410 `run_events_gone` after
the log's hour); `POST /v1/agent/runs/{id}/cancel` asks the run to stop (202).
"""

from collections.abc import AsyncIterable
from http import HTTPStatus
from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import Field, model_validator

from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.run_streams import RunStreams
from shosai.features.agent.application.surface_digest import Subject, SubjectKind
from shosai.features.agent.application.turn_start import (
    Page,
    Replacement,
    TurnRequest,
    TurnStarter,
)
from shosai.features.agent.channels.http.shapes import Strict
from shosai.features.agent.domain.attachments import MAX_ATTACHMENTS
from shosai.features.agent.domain.stream import StreamEvent
from shosai.features.agent.domain.threads import QUESTION_MAX, SURFACE_PATH_MAX, TurnKind
from shosai.features.identity.contracts import Principal, bearer_principal

LOCALE_MAX = 16
PATH_MAX = SURFACE_PATH_MAX
# Сырой текст длиннее вопроса на поля по краям: обрезанный пробелами вопрос проверяет домен.
TEXT_MAX = QUESTION_MAX * 2


class SubjectIn(Strict):
    """What the page shows: a meeting, a task, a board or a file."""

    kind: SubjectKind
    id: UUID


class SurfaceIn(Strict):
    """The cabinet page the person asks from."""

    path: str = Field(max_length=PATH_MAX, description="The cabinet path, such as /app/notes.")
    subject: SubjectIn | None = None


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
    surface: SurfaceIn | None = None
    regenerate_of: UUID | None = Field(
        default=None, description="The thread's last question, answered again."
    )
    edit_of: UUID | None = Field(
        default=None, description="The thread's last question, rewritten to `text` and answered."
    )
    upload_ids: list[UUID] = Field(
        default_factory=list,
        max_length=MAX_ATTACHMENTS,
        description="Ready `leo_attachment` uploads attached to a new question, at most five.",
    )

    @model_validator(mode="after")
    def one_replacement(self) -> Self:
        """A turn regenerates or edits, never both; only a new question brings attachments."""
        if self.regenerate_of is not None and self.edit_of is not None:
            message = "regenerate_of and edit_of exclude each other"
            raise ValueError(message)
        again = self.regenerate_of is not None or self.edit_of is not None
        if again and self.upload_ids:
            message = "attachments come only with a new question"
            raise ValueError(message)
        if len(set(self.upload_ids)) != len(self.upload_ids):
            message = "an upload is attached once"
            raise ValueError(message)
        return self

    def request(self) -> TurnRequest:
        """The turn as admission reads it."""
        subject = self.surface.subject if self.surface else None
        page = Page(
            self.surface.path if self.surface else None,
            Subject(subject.kind, subject.id) if subject else None,
        )
        if self.regenerate_of is not None:
            again = Replacement(TurnKind.REGENERATE, self.regenerate_of)
        elif self.edit_of is not None:
            again = Replacement(TurnKind.EDIT, self.edit_of)
        else:
            again = Replacement(TurnKind.NEW, None)
        return TurnRequest(
            self.text, self.locale, self.supersede, page, again, tuple(self.upload_ids)
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
        return await starter.start(principal, thread_id, body.request(), idempotency_key)

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
