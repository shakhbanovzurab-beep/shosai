"""`tasks.update`, `tasks.complete` and `tasks.move` bound: one task each (tasks step 8).

`plan` reads the task as the person may read it, refuses a Jira card and a change that breaks
the task's rules, and freezes the task with the fields it sends; `preview` names the task and
what changes; `execute` runs only through the Action Gateway, in the task's space, once per
item key with the audit event (`ActionItems`), through the cabinet's own edit — field
presence, Leo's marks, the next recurring task, the stopwatch, the boards' revisions.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.bindings import WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import PlannedEffect, Preview, ToolError, ToolResult
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from shosai.features.tasks.application.board_access import owned_board
from shosai.features.tasks.application.leo_writes import jira_refused, move_card
from shosai.features.tasks.application.placements import CardSpot, column_kind
from shosai.features.tasks.application.scoping import Scoping, locked_task, rule_failure
from shosai.features.tasks.application.task_edits import Edit, TaskEdits
from shosai.features.tasks.channels import agent_previews as words
from shosai.features.tasks.channels.agent_previews import CLEARED
from shosai.features.tasks.channels.agent_task_change_fields import (
    change_of,
    changed,
    sent_of,
    update_params,
)
from shosai.features.tasks.channels.agent_tool_errors import person, tool_error
from shosai.features.tasks.channels.agent_write_tools import (
    COMPLETE,
    MOVE,
    UPDATE,
    CompleteTask,
    MoveTask,
    TaskChanged,
    TaskMoved,
    UpdateTask,
)
from shosai.features.tasks.domain.changes import (
    Schedule,
    TaskChange,
    checked_change,
    schedule_after,
)
from shosai.features.tasks.domain.tasks import Assignee, TaskRuleError, TaskStatus
from shosai.features.tasks.infrastructure.board_records import BoardColumnRecord, BoardRecord
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE, TaskRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

type Effect[O] = Callable[[AsyncSession, TaskRecord], Awaitable[O]]


class TaskChanges:
    """Plans, previews and applies Leo's change, tick and move of one task."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        services: tuple[TaskEdits, ActionItems],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._edits, self._items = services
        self._clock = clock
        self._scoping = Scoping(transactions, ports)

    def bound(self) -> tuple[
        WriteTool[UpdateTask, TaskChanged], WriteTool[CompleteTask, TaskChanged],
        WriteTool[MoveTask, TaskMoved],
    ]:  # fmt: skip
        """The three tools."""
        return (
            WriteTool(UPDATE, self.plan_update, self.preview_update, self.execute_update),
            WriteTool(COMPLETE, self.plan_complete, self.preview_complete, self.execute_complete),
            WriteTool(MOVE, self.plan_move, self.preview_move, self.execute_move),
        )

    async def plan_update(
        self, args: UpdateTask, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the task and the fields that change, checked against it now."""
        sent = sent_of(args)

        async def check(session: AsyncSession, record: TaskRecord) -> None:
            change, edit = change_of(sent)
            try:
                checked = checked_change(change, record.org_id)
                current = Schedule(record.starts_on, record.due_on, None)
                schedule_after(current, checked, self._clock().date())
            except TaskRuleError as error:
                raise rule_failure(error) from error
            if edit.sent_assignee_id and isinstance(checked.assignee, Assignee):
                await self._scoping.check_member(session, record.org_id, checked.assignee.user_id)

        return await self._plan(args.task_id, context, check, {"fields": sent})

    async def preview_update(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: which task, and what each sent field becomes."""
        raw = planned.data["fields"]
        sent = raw if isinstance(raw, dict) else {}
        title = await self._title(context, UUID(planned.targets[0]))
        assignee = sent.get("assignee_name")
        if sent.get("assignee_id") is not None:
            member = UUID(str(sent["assignee_id"]))
            async with self._transactions.begin(person(context).scope(), read_only=True) as session:
                names = await self._ports.get(ACCOUNT_PROFILE_READER).names(session, [member])
            assignee = names.get(member)
        elif ("assignee_id" in sent or "assignee_name" in sent) and assignee is None:
            assignee = CLEARED
        params = update_params(title, sent, None if assignee is None else str(assignee))
        return Preview(words.UPDATE.key, params)

    async def execute_update(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[TaskChanged]:
        """Change the planned task's planned fields only."""
        raw = planned.data["fields"]
        sent = raw if isinstance(raw, dict) else {}

        async def effect(session: AsyncSession, record: TaskRecord) -> TaskChanged:
            await self._edits.apply(session, person(context).user_id, record, change_of(sent)[1])
            return changed(record)

        return await self._execute(planned, context, (key, UPDATE.name, TaskChanged), effect)

    async def plan_complete(
        self, args: CompleteTask, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the task and whether it becomes done."""

        async def nothing(session: AsyncSession, record: TaskRecord) -> None:
            del session, record

        return await self._plan(args.task_id, context, nothing, {"done": args.done})

    async def preview_complete(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: which task, done or open again."""
        title = await self._title(context, UUID(planned.targets[0]))
        wording = words.COMPLETE if planned.data["done"] else words.REOPEN
        return Preview(wording.key, {"title": title})

    async def execute_complete(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[TaskChanged]:
        """Mark the planned task done, or open it again."""
        status = TaskStatus.DONE if planned.data["done"] else TaskStatus.TODO

        async def effect(session: AsyncSession, record: TaskRecord) -> TaskChanged:
            if record.status != status.value:
                edit = Edit(change=TaskChange(status=status))
                await self._edits.apply(session, person(context).user_id, record, edit)
            return changed(record)

        return await self._execute(planned, context, (key, COMPLETE.name, TaskChanged), effect)

    async def plan_move(self, args: MoveTask, context: ToolContext) -> PlannedEffect | ToolError:
        """Freeze the task and the spot of the person's board it goes to."""
        viewer = person(context).user_id

        async def check(session: AsyncSession, record: TaskRecord) -> None:
            del record
            await owned_board(session, viewer, args.board_id)
            await column_kind(session, args.board_id, args.column_id)

        data: dict[str, JsonValue] = {
            "board_id": str(args.board_id), "column_id": str(args.column_id),
            "position": args.position,
        }  # fmt: skip
        return await self._plan(args.task_id, context, check, data)

    async def preview_move(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: which task, to which board and column."""
        title = await self._title(context, UUID(planned.targets[0]))
        board_id, column_id = (
            UUID(str(planned.data["board_id"])),
            UUID(str(planned.data["column_id"])),
        )
        async with self._transactions.begin(person(context).scope(), read_only=True) as session:
            board = await session.scalar(select(BoardRecord.name).where(BoardRecord.id == board_id))
            column = await session.scalar(
                select(BoardColumnRecord.title).where(BoardColumnRecord.id == column_id)
            )
        return Preview(words.MOVE.key, {"title": title, "board": board, "column": column})

    async def execute_move(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[TaskMoved]:
        """Move the person's card of the planned task to the planned spot only."""
        spot = CardSpot(
            UUID(str(planned.data["board_id"])), UUID(str(planned.data["column_id"])),
            int(str(planned.data["position"])),
        )  # fmt: skip

        async def effect(session: AsyncSession, record: TaskRecord) -> TaskMoved:
            principal = person(context)
            status = await move_card(session, principal, record, (spot, self._edits), self._clock())
            return TaskMoved(
                task_id=record.id, board_id=spot.board_id, column_id=spot.column_id, status=status
            )

        return await self._execute(planned, context, (key, MOVE.name, TaskMoved), effect)

    async def _plan(
        self,
        task_id: UUID,
        context: ToolContext,
        check: Effect[None],
        data: dict[str, JsonValue],
    ) -> PlannedEffect | ToolError:
        principal = person(context)
        try:
            scope = await self._scoping.space_of(principal, task_id)
            async with self._transactions.begin(scope, read_only=True) as session:
                record = await locked_task(
                    session, self._ports, principal.user_id, task_id, lock=False
                )
                jira_refused(record)
                await check(session, record)
        except AppError as error:
            return tool_error(error)
        return PlannedEffect((str(task_id),), data, org_id=record.org_id)

    async def _execute[O: BaseModel](
        self,
        planned: PlannedEffect,
        context: ToolContext,
        item: tuple[str, str, type[O]],
        effect: Effect[O],
    ) -> ToolResult[O]:
        principal, task_id = person(context), UUID(planned.targets[0])
        key, tool, output = item
        try:
            scope = await self._scoping.space_of(principal, task_id)
            async with self._transactions.begin(scope) as session:
                record = await locked_task(session, self._ports, principal.user_id, task_id)
                jira_refused(record)
                outcome = await self._items.once(
                    session, (key, tool, 1), output, lambda: effect(session, record)
                )
        except AppError as error:
            return ToolResult(error=tool_error(error))
        return ToolResult(outcome)

    async def _title(self, context: ToolContext, task_id: UUID) -> str | None:
        """The task's title for the card; None when it went since the plan."""
        principal = person(context)
        readable = self._ports.get(ACCESS_POLICY).readable(TASK_RESOURCE, Viewer(principal.user_id))
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            title: str | None = await session.scalar(
                select(TaskRecord.title).where(TaskRecord.id == task_id, readable)
            )
            return title
