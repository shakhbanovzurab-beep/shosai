"""`tasks.create` bound: a batch planned whole, previewed, made whole once (tasks step 8).

`plan` checks every task of the batch in the space it names and freezes the checked drafts;
`preview` counts them and names the space and the board; `execute` runs only through the
Action Gateway and makes them in one transaction of the space, once per item key, with the
audit event (`ActionItems`). The model's arguments never name a chat: a batch from a team
chat's message is planned by the server (`plan_from_chat`), which freezes the chat with it.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Final
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import select

from shosai.core.agent_tools.bindings import WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import PlannedEffect, Preview, ToolError, ToolResult
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.kernel.errors import AppError
from shosai.features.tasks.application.leo_writes import LeoBatch, checked_batch, make_batch
from shosai.features.tasks.application.scoping import scope_in
from shosai.features.tasks.application.task_writes import NewTask, TaskWrites
from shosai.features.tasks.channels.agent_tool_errors import person, tool_error
from shosai.features.tasks.channels.agent_write_tools import (
    CREATE,
    CreateTasks,
    TaskDraftArgs,
    TasksCreated,
)
from shosai.features.tasks.domain.chat_source import ChatOrigin, Messenger
from shosai.features.tasks.domain.tasks import Assignee, Priority
from shosai.features.tasks.infrastructure.board_records import BoardRecord

PREVIEW_KEY: Final = "agent.tasks.create"


def batch_of(args: CreateTasks, chat: ChatOrigin | None = None) -> LeoBatch:
    """The batch the arguments ask for."""
    return LeoBatch(
        tuple(_draft(task) for task in args.tasks), args.workspace_id, args.board_id, chat
    )


def _draft(task: TaskDraftArgs) -> NewTask:
    return NewTask(
        title=task.title, description=task.description, priority=task.priority,
        starts_on=task.starts_on, due_on=task.due_on, project_id=task.project_id,
        assignee=Assignee(user_id=task.assignee_id, name=task.assignee_name),
    )  # fmt: skip


def frozen(batch: LeoBatch) -> PlannedEffect:
    """The checked batch as the agent keeps it until approval."""
    target = "personal" if batch.workspace_id is None else str(batch.workspace_id)
    data: dict[str, JsonValue] = {
        "workspace_id": None if batch.workspace_id is None else str(batch.workspace_id),
        "board_id": None if batch.board_id is None else str(batch.board_id),
        "tasks": [_draft_json(draft) for draft in batch.drafts],
        "chat": None if batch.chat is None else _chat_json(batch.chat),
    }
    return PlannedEffect((target,), data)


def thawed(planned: PlannedEffect) -> LeoBatch:
    """The batch back from its plan."""
    data = planned.data
    raw_tasks = data["tasks"]
    tasks = raw_tasks if isinstance(raw_tasks, list) else []
    return LeoBatch(
        tuple(_draft_of(item) for item in tasks if isinstance(item, dict)),
        _uuid(data.get("workspace_id")), _uuid(data.get("board_id")),
        _chat_of(data.get("chat")),
    )  # fmt: skip


def _draft_json(draft: NewTask) -> dict[str, JsonValue]:
    return {
        "title": draft.title, "description": draft.description,
        "priority": None if draft.priority is None else draft.priority.value,
        "starts_on": None if draft.starts_on is None else draft.starts_on.isoformat(),
        "due_on": None if draft.due_on is None else draft.due_on.isoformat(),
        "assignee_id": None if draft.assignee.user_id is None else str(draft.assignee.user_id),
        "assignee_name": draft.assignee.name,
        "project_id": None if draft.project_id is None else str(draft.project_id),
    }  # fmt: skip


def _draft_of(item: Mapping[str, JsonValue]) -> NewTask:
    priority = item.get("priority")
    return NewTask(
        title=str(item["title"]), description=str(item.get("description") or ""),
        priority=None if priority is None else Priority(str(priority)),
        starts_on=_day(item.get("starts_on")), due_on=_day(item.get("due_on")),
        project_id=_uuid(item.get("project_id")),
        assignee=Assignee(
            user_id=_uuid(item.get("assignee_id")),
            name=None if item.get("assignee_name") is None else str(item["assignee_name"]),
        ),
    )  # fmt: skip


def _chat_json(chat: ChatOrigin) -> dict[str, JsonValue]:
    return {
        "connection_id": None if chat.connection_id is None else str(chat.connection_id),
        "messenger": chat.messenger.value, "chat_title": chat.chat_title,
        "message_url": chat.message_url, "message_at": chat.message_at.isoformat(),
    }  # fmt: skip


def _chat_of(raw: JsonValue) -> ChatOrigin | None:
    if not isinstance(raw, dict):
        return None
    url = raw.get("message_url")
    return ChatOrigin(
        _uuid(raw.get("connection_id")), Messenger(str(raw["messenger"])),
        str(raw["chat_title"]), None if url is None else str(url),
        datetime.fromisoformat(str(raw["message_at"])),
    )  # fmt: skip


def _uuid(raw: JsonValue) -> UUID | None:
    return None if raw is None else UUID(str(raw))


def _day(raw: JsonValue) -> date | None:
    return None if raw is None else date.fromisoformat(str(raw))


class TaskCreates:
    """Plans, previews and makes Leo's batches of tasks."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[TaskWrites, ActionItems],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._writes, self._items = services
        self._clock = clock

    def bound(self) -> WriteTool[CreateTasks, TasksCreated]:
        """The tool."""
        return WriteTool(CREATE, self.plan, self.preview, self.execute)

    async def plan(self, args: CreateTasks, context: ToolContext) -> PlannedEffect | ToolError:
        """The batch the model asks for, checked whole; never from a chat."""
        return await self._plan(batch_of(args), context)

    async def plan_from_chat(
        self, args: CreateTasks, chat: ChatOrigin, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """A batch from a team chat's message, planned by the server with its chat (TK-D13)."""
        return await self._plan(batch_of(args, chat), context)

    async def _plan(self, batch: LeoBatch, context: ToolContext) -> PlannedEffect | ToolError:
        principal = person(context)
        scope = scope_in(principal, batch.workspace_id)
        try:
            async with self._transactions.begin(scope, read_only=True) as session:
                checked = await checked_batch(session, self._writes, principal, batch)
        except AppError as error:
            return tool_error(error)
        return frozen(checked)

    async def preview(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: how many tasks, the first one's title, and the board."""
        batch = thawed(planned)
        principal = person(context)
        board = None
        if batch.board_id is not None:
            async with self._transactions.begin(principal.scope(), read_only=True) as session:
                board = await session.scalar(
                    select(BoardRecord.name).where(BoardRecord.id == batch.board_id)
                )
        first = batch.drafts[0].title if batch.drafts else None
        params = {"count": len(batch.drafts), "first": first, "board": board,
                  "workspace": batch.workspace_id is not None}  # fmt: skip
        return Preview(PREVIEW_KEY, params)

    async def execute(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[TasksCreated]:
        """Make the planned batch, whole, once per key."""
        batch, principal = thawed(planned), person(context)
        now = self._clock()
        item = (key, CREATE.name, len(batch.drafts))
        try:
            async with self._transactions.begin(scope_in(principal, batch.workspace_id)) as session:

                async def effect() -> TasksCreated:
                    made = await make_batch(session, self._writes, principal, batch, now)
                    return TasksCreated(task_ids=list(made))

                outcome = await self._items.once(session, item, TasksCreated, effect)
        except AppError as error:
            return ToolResult(error=tool_error(error))
        return ToolResult(outcome)
