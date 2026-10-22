"""A task's checklist and comments (`/v1/tasks/{id}/subtasks*`, `/comments*`; tasks plan §3.12).

Whoever may read a task changes its checklist and writes its comments; only the author edits
or deletes a comment (`not_comment_author`). Errors use the platform's envelope with the
codes the cabinet words: `task_not_found`, `subtask_not_found`, `comment_not_found`,
`subtasks_full`, `jira_unsupported`, `title_required`, `title_too_long`, `comment_too_long`,
`validation_error`, `invalid_cursor`, `idempotency_key_reused`.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from shosai.core.pagination.page import Page, PageRequest, page_parameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.tasks.application.comments import Comments, CommentView
from shosai.features.tasks.application.subtasks import SubtaskChange, Subtasks
from shosai.features.tasks.application.views import SubtaskView
from shosai.features.tasks.channels.http.detail_models import SubtaskOut
from shosai.features.tasks.channels.http.shapes import OptionalIdempotencyKey, Strict, invalid

COMMENTS_PAGE = Depends(page_parameters(default=50, maximum=100))


class SubtaskCreateBody(Strict):
    """A new line of the checklist, at its position or at the end."""

    title: str
    position: int | None = Field(default=None, ge=0)


class SubtaskPatchBody(Strict):
    """A change of a line by field presence; none of its fields is cleared."""

    title: str | None = None
    done: bool | None = None
    position: int | None = Field(default=None, ge=0)


class CommentBody(Strict):
    """A comment's text."""

    body: str


class CommentAuthorOut(BaseModel):
    """Who wrote a comment, and whether it is the reader."""

    user_id: UUID
    name: str
    is_you: bool


class CommentOut(BaseModel):
    """A comment on a task."""

    id: UUID
    author: CommentAuthorOut
    body: str
    created_at: datetime
    edited_at: datetime | None


def subtask_out(view: SubtaskView) -> SubtaskOut:
    """A line of the checklist."""
    return SubtaskOut(id=view.id, title=view.title, done=view.done)


def comment_out(view: CommentView) -> CommentOut:
    """A comment as the cabinet reads it."""
    author = CommentAuthorOut(
        user_id=view.author_user_id, name=view.author_name, is_you=view.is_you
    )
    return CommentOut(
        id=view.id, author=author, body=view.body, created_at=view.created_at,
        edited_at=view.edited_at,
    )  # fmt: skip


def change_of(body: SubtaskPatchBody) -> SubtaskChange:
    """The change a body asks for; a field sent as null is refused."""
    if any(getattr(body, name) is None for name in body.model_fields_set):
        raise invalid()
    return SubtaskChange(title=body.title, done=body.done, position=body.position)


def build_threads_router(services: tuple[Subtasks, Comments], ports: PortDirectory) -> APIRouter:
    """The routes of tasks' checklists and comments."""
    subtasks, comments = services
    router = APIRouter(prefix="/v1/tasks/{task_id}", tags=["tasks"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.post("/subtasks", status_code=HTTPStatus.CREATED)
    async def create_subtask(
        principal: person, task_id: UUID, body: SubtaskCreateBody
    ) -> SubtaskOut:
        """Add a line at its position, the end by default; 100 at most."""
        return subtask_out(await subtasks.create(principal, task_id, body.title, body.position))

    @router.patch("/subtasks/{subtask_id}")
    async def change_subtask(
        principal: person, task_id: UUID, subtask_id: UUID, body: SubtaskPatchBody
    ) -> SubtaskOut:
        """Rename, tick or move a line."""
        change = change_of(body)
        return subtask_out(await subtasks.change(principal, task_id, subtask_id, change))

    @router.delete("/subtasks/{subtask_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_subtask(principal: person, task_id: UUID, subtask_id: UUID) -> Response:
        """Remove a line."""
        await subtasks.delete(principal, task_id, subtask_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.get("/comments")
    async def list_comments(
        principal: person, task_id: UUID, page: Annotated[PageRequest, COMMENTS_PAGE]
    ) -> Page[CommentOut]:
        """A page of the task's comments, newest first."""
        found = await comments.page(principal, task_id, page)
        return Page(
            items=[comment_out(view) for view in found.items], next_cursor=found.next_cursor
        )

    @router.post("/comments", status_code=HTTPStatus.CREATED)
    async def create_comment(
        principal: person,
        task_id: UUID,
        body: CommentBody,
        idempotency_key: OptionalIdempotencyKey = None,
    ) -> CommentOut:
        """Write a comment; once per `Idempotency-Key` when one is sent."""
        return comment_out(await comments.create(principal, task_id, body.body, idempotency_key))

    @router.patch("/comments/{comment_id}")
    async def edit_comment(
        principal: person, task_id: UUID, comment_id: UUID, body: CommentBody
    ) -> CommentOut:
        """Edit one's own comment."""
        return comment_out(await comments.edit(principal, task_id, comment_id, body.body))

    @router.delete("/comments/{comment_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_comment(principal: person, task_id: UUID, comment_id: UUID) -> Response:
        """Delete one's own comment."""
        await comments.delete(principal, task_id, comment_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
