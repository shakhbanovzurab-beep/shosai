"""Threads and their history: `/v1/agent/threads*` (agent plan §3.3, step 4).

The cabinet lists a context's threads (Personal or a workspace), creates one at the first
question of a new chat, renames and deletes them, and reads a thread's history by cursor.
Errors use the platform's envelope with the codes the cabinet words: `thread_not_found`
(another person's thread or a departed workspace's), `workspace_not_found`,
`scope_unavailable` (a hub's threads, until hubs), `scope_invalid`, `title_invalid`,
`invalid_cursor`, `idempotency_key_reused`, `validation_error`.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import Field

from shosai.core.agent_tools.sources import SourceKind
from shosai.core.idempotency.http import IdempotencyKeyHeader
from shosai.core.kernel.errors import AppError
from shosai.core.pagination.page import Page, PageParameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.history import History, MessageView
from shosai.features.agent.application.threads import Threads, ThreadView
from shosai.features.agent.channels.http.actions import ProposalOut
from shosai.features.agent.channels.http.shapes import Out, Strict
from shosai.features.agent.domain.feedback import Rating
from shosai.features.agent.domain.threads import (
    AnswerStatus,
    HistoryRole,
    ScopeKind,
    StepStatus,
    ThreadRuleError,
    ThreadScope,
    check_available,
)
from shosai.features.identity.contracts import Principal, bearer_principal


class ScopeIn(Strict):
    """The space of a new thread: Personal, or a workspace the person belongs to."""

    kind: ScopeKind
    workspace_id: UUID | None = None


class ThreadCreateBody(Strict):
    """A new thread."""

    scope: ScopeIn


class ThreadPatchBody(Strict):
    """A thread's new title, 1 to 120 characters."""

    title: str


class ScopeOut(Out):
    """The space a thread belongs to."""

    kind: ScopeKind
    workspace_id: UUID | None
    hub_id: UUID | None


class ThreadOut(Out):
    """A thread; `title` is null until its first question names it."""

    id: UUID
    scope: ScopeOut
    title: str | None
    last_activity_at: datetime
    created_at: datetime


class StepOut(Out):
    """A step of an answer: the tool's name or a reasoning code, the argument it showed, how it
    ended and how long it took."""

    id: str
    activity: str
    detail: str | None
    status: StepStatus
    duration_ms: int | None


class AnswerSourceOut(Out):
    """A source of an answer, the n-th counting from one: what it is, the space it belongs to
    ("Personal" in the person's language or the workspace's name), where inside it and the
    quote the answer rests on; `highlight` stays empty while the quote is shown whole."""

    id: str
    kind: SourceKind
    title: str
    space: str
    locator: str | None
    quote: str
    highlight: list[str]


class ArtifactOut(Out):
    """A result read apart from the answer: a team chat's digest, by its reference (AG-R1)."""

    kind: Literal["chat_digest"]
    ref: str = Field(description="The digest's id; the cabinet reads it from chats.")
    alt: str = Field(description="What it is, for those who do not see it.")
    workspace_id: UUID
    chat_id: UUID


class QuestionAttachmentOut(Out):
    """A file attached to a question."""

    id: UUID
    name: str
    size: int
    type: str


class MessageOut(Out):
    """A row of the history: a question, an answer (with how it ended, the steps it took, its
    sources and its cards) or a server's note (with the card it tells about)."""

    id: UUID
    role: HistoryRole
    text: str
    status: AnswerStatus | None
    created_at: datetime
    duration_ms: int | None
    steps: list[StepOut]
    sources: list[AnswerSourceOut]
    actions: list[ProposalOut] = Field(description="The cards the answer proposed, as they stand.")
    artifacts: list[ArtifactOut] = Field(description="What the tools handed over, by reference.")
    feedback: Rating | None = Field(description="The person's rating of the answer, if any.")
    attachments: list[QuestionAttachmentOut] = Field(
        description="The files attached to a question."
    )


def scope_of(kind: ScopeKind, workspace_id: UUID | None) -> ThreadScope:
    """The space a request names: a hub is 422 `scope_unavailable` until hubs; a workspace
    without its id, or Personal with one, is 422 `scope_invalid`."""
    try:
        check_available(kind)
        return ThreadScope(kind, org_id=workspace_id)
    except ThreadRuleError as error:
        raise AppError(error.rule.value, HTTPStatus.UNPROCESSABLE_CONTENT) from error


def thread_out(view: ThreadView) -> ThreadOut:
    """A thread as the cabinet reads it."""
    scope = ScopeOut(kind=view.scope.kind, workspace_id=view.scope.org_id, hub_id=view.scope.hub_id)
    return ThreadOut(
        id=view.id, scope=scope, title=view.title, last_activity_at=view.last_activity_at,
        created_at=view.created_at,
    )  # fmt: skip


def message_out(view: MessageView) -> MessageOut:
    """A message as the cabinet reads it."""
    steps = [
        StepOut(
            id=step.id, activity=step.activity, detail=step.detail,
            status=StepStatus(step.status), duration_ms=step.duration_ms,
        )
        for step in view.steps
    ]  # fmt: skip
    return MessageOut(
        id=view.id, role=view.role, text=view.text, status=view.status,
        created_at=view.created_at, duration_ms=view.duration_ms, steps=steps,
        sources=[
            AnswerSourceOut(
                id=source.id, kind=source.kind, title=source.title, space=source.space,
                locator=source.locator, quote=source.quote, highlight=[],
            )
            for source in view.sources
        ],
        actions=[ProposalOut.model_validate(card) for card in view.actions],
        artifacts=[ArtifactOut.model_validate(artifact) for artifact in view.artifacts],
        feedback=view.feedback,
        attachments=[QuestionAttachmentOut.model_validate(item) for item in view.attachments],
    )  # fmt: skip


def build_threads_router(services: tuple[Threads, History], ports: PortDirectory) -> APIRouter:
    """The routes of the person's threads and their history."""
    threads, history = services
    router = APIRouter(prefix="/v1/agent/threads", tags=["agent"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.get("")
    async def list_threads(
        principal: person,
        page: PageParameters,
        scope: Annotated[ScopeKind, Query(description="The context's space.")],
        workspace_id: Annotated[
            UUID | None, Query(description="The workspace, with `scope=workspace`.")
        ] = None,
    ) -> Page[ThreadOut]:
        """A page of one space's threads, newest activity first."""
        found = await threads.page(principal, scope_of(scope, workspace_id), page)
        return Page(items=[thread_out(view) for view in found.items], next_cursor=found.next_cursor)

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_thread(
        principal: person, body: ThreadCreateBody, idempotency_key: IdempotencyKeyHeader
    ) -> ThreadOut:
        """A new thread in a space; a retry with the same key answers the same thread."""
        space = scope_of(body.scope.kind, body.scope.workspace_id)
        return thread_out(await threads.create(principal, space, idempotency_key))

    @router.get("/{thread_id}")
    async def get_thread(principal: person, thread_id: UUID) -> ThreadOut:
        """One of the person's threads."""
        return thread_out(await threads.get(principal, thread_id))

    @router.patch("/{thread_id}")
    async def rename_thread(principal: person, thread_id: UUID, body: ThreadPatchBody) -> ThreadOut:
        """Rename a thread."""
        return thread_out(await threads.rename(principal, thread_id, body.title))

    @router.delete("/{thread_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_thread(principal: person, thread_id: UUID) -> Response:
        """Delete a thread with its whole conversation."""
        await threads.delete(principal, thread_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.get("/{thread_id}/messages")
    async def list_messages(
        principal: person, thread_id: UUID, page: PageParameters
    ) -> Page[MessageOut]:
        """A page of the thread's history, newest first."""
        found = await history.page(principal, thread_id, page)
        return Page(
            items=[message_out(view) for view in found.items], next_cursor=found.next_cursor
        )

    return router
