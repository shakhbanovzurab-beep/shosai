"""The one task API for every space (`/v1/tasks*`; TK-D1, tasks plan §3.3, §3.8, §3.11).

A list pages the tasks the person may read — in Personal and in every workspace they belong
to — by due day or by last change; Today is their personal day (TK-D11). A task is read,
changed by field presence and deleted at once; a batch is deleted all or none. Errors use
the platform's envelope with the codes the cabinet words: `task_not_found`,
`task_not_deletable`, `workspace_not_found`, `attachment_not_found`, `title_required`,
`title_too_long`, `description_too_long`, `range_invalid`, `recurrence_invalid`,
`validation_error`, `invalid_cursor`, `idempotency_key_reused`.
"""

from datetime import date
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from shosai.core.pagination.page import Page, PageRequest, page_parameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.tasks.application.task_edits import TaskEdits
from shosai.features.tasks.application.task_query import StatusFilter, TaskQuery, TaskSort
from shosai.features.tasks.application.task_reads import TaskReads
from shosai.features.tasks.application.task_writes import NewTask, TaskWrites
from shosai.features.tasks.channels.http.detail_models import TaskDetail, TaskItem, TodayOut
from shosai.features.tasks.channels.http.shapes import (
    OptionalIdempotencyKey,
    TaskCreateBody,
    TaskPatchBody,
    TasksDeleteBody,
    detail_out,
    edit_of,
    invalid,
    item_out,
    schedule_of,
)
from shosai.features.tasks.domain.tasks import Assignee

LIST_PAGE = Depends(page_parameters(default=50, maximum=200))


class TaskListParams(BaseModel):
    """What a list of tasks holds and its order."""

    workspace_id: UUID | None = None
    personal: bool = False
    assignee: str | None = Field(default=None, max_length=40)
    status: StatusFilter | None = None
    meeting_id: UUID | None = None
    project_id: UUID | None = None
    due_before: date | None = None
    q: str | None = Field(default=None, min_length=1, max_length=200)
    sort: TaskSort = TaskSort.DUE


def assignee_of(raw: str | None) -> str | UUID | None:
    """`me`, `none` or a member's id; anything else is refused."""
    if raw is None or raw in {"me", "none"}:
        return raw
    try:
        return UUID(raw)
    except ValueError as error:
        raise invalid() from error


def build_tasks_router(
    services: tuple[TaskReads, TaskWrites, TaskEdits], ports: PortDirectory
) -> APIRouter:
    """The person's task routes."""
    reads, writes, edits = services
    router = APIRouter(prefix="/v1/tasks", tags=["tasks"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.get("")
    async def list_tasks(
        principal: person,
        page: Annotated[PageRequest, LIST_PAGE],
        params: Annotated[TaskListParams, Query()],
    ) -> Page[TaskItem]:
        """A page of the tasks the person may read, by due day (no day last) or newest change."""
        query = TaskQuery(
            workspace_id=params.workspace_id, personal=params.personal,
            assignee=assignee_of(params.assignee), status=params.status,
            meeting_id=params.meeting_id, project_id=params.project_id,
            due_before=params.due_before, text=params.q, sort=params.sort,
        )  # fmt: skip
        found = await reads.page(principal, query, page)
        return Page(items=[item_out(view) for view in found.items], next_cursor=found.next_cursor)

    @router.get("/today")
    async def read_today(principal: person, day: date | None = None) -> TodayOut:
        """Open personal tasks due on or before the day, and those completed on it."""
        return TodayOut(items=[item_out(view) for view in await reads.today(principal, day)])

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_task(
        principal: person,
        body: TaskCreateBody,
        idempotency_key: OptionalIdempotencyKey = None,
    ) -> TaskDetail:
        """A task made by hand; once per `Idempotency-Key` when one is sent."""
        if body.assignee_id is not None and body.assignee_name is not None:
            raise invalid()
        draft = NewTask(
            title=body.title, description=body.description, status=body.status,
            priority=body.priority, starts_on=body.starts_on, due_on=body.due_on,
            recurrence=schedule_of(body.recurrence), workspace_id=body.workspace_id,
            assignee=Assignee(body.assignee_id, body.assignee_name), project_id=body.project_id,
        )  # fmt: skip
        return detail_out(await writes.create(principal, draft, idempotency_key))

    @router.post("/delete", status_code=HTTPStatus.NO_CONTENT)
    async def delete_tasks(principal: person, body: TasksDeleteBody) -> Response:
        """Delete tasks after the cabinet's Undo, all or none."""
        await writes.delete(principal, body.task_ids)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.get("/{task_id}")
    async def read_task(principal: person, task_id: UUID) -> TaskDetail:
        """A task the person may read, as its panel shows it."""
        return detail_out(await reads.detail(principal, task_id))

    @router.patch("/{task_id}")
    async def change_task(principal: person, task_id: UUID, body: TaskPatchBody) -> TaskDetail:
        """Change a task by field presence: a field left out stays, `null` clears it."""
        return detail_out(await edits.change(principal, task_id, edit_of(body)))

    @router.delete("/{task_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_task(principal: person, task_id: UUID) -> Response:
        """Delete a task at once; the cabinet's Undo delays the call."""
        await writes.delete(principal, [task_id])
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
