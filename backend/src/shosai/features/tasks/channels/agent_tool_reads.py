"""Leo's task reads bound to the toolset's specs: arguments in, results out (tasks step 7).

A board the person does not have is `not_found`; anything else the model sends is already
checked by the arguments' schema. A running stopwatch's time is counted up to now.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from shosai.core.agent_tools.bindings import AgentTool, ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import ToolError, ToolErrorCode, ToolResult
from shosai.features.tasks.application.leo_reads import BoardRead as BoardView
from shosai.features.tasks.application.leo_reads import Found, LeoReads, TaskSearch
from shosai.features.tasks.application.views import TaskView
from shosai.features.tasks.channels.agent_tool_models import (
    BoardCard,
    BoardColumnCards,
    BoardRead,
    BoardRef,
    FoundTask,
    FoundTasks,
    ListBoard,
    OnBoard,
    SearchTasks,
    TimeSpent,
    WhoDoes,
    WorkspaceRef,
)
from shosai.features.tasks.channels.agent_tools import LIST_BOARD, SEARCH_TASKS
from shosai.features.tasks.domain.clocks import ms_between
from shosai.features.tasks.domain.tasks import TaskStatus


class TaskToolReads:
    """The handlers of `tasks.search` and `tasks.list_board`."""

    def __init__(
        self, reads: LeoReads, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._reads = reads
        self._clock = clock

    async def search(self, args: SearchTasks, context: ToolContext) -> ToolResult[FoundTasks]:
        """The tasks found."""
        search = TaskSearch(
            text=args.query, status=args.status, due=args.due, workspace_id=args.workspace_id,
            personal=args.personal, meeting_id=args.meeting_id, board_id=args.board_id,
            mine=args.mine, limit=args.limit,
        )  # fmt: skip
        found = await self._reads.search(context.scope, search)
        tasks = [self._found(view, found, context) for view in found.tasks]
        return ToolResult(output=FoundTasks(tasks=tasks, more=found.more))

    async def list_board(self, args: ListBoard, context: ToolContext) -> ToolResult[BoardRead]:
        """The board as the person sees it."""
        board = await self._reads.board(context.scope, args.board_id)
        if board is None:
            return ToolResult(error=ToolError(ToolErrorCode.NOT_FOUND))
        return ToolResult(output=_board_out(board))

    def _found(self, view: TaskView, found: Found, context: ToolContext) -> FoundTask:
        card = view.card
        open_and_late = card.due_on is not None and card.due_on < found.today
        return FoundTask(
            task_id=card.id, title=card.title, status=card.status, priority=card.priority,
            starts_on=card.starts_on, due_on=card.due_on,
            overdue=card.status is not TaskStatus.DONE and open_and_late,
            who=_who(view, context), workspace=_workspace(view), source=view.source,
            meeting_id=view.meeting_id, recurring=card.recurring,
            on_board=_on_board(view, found), time=self._time(view),
        )  # fmt: skip

    def _time(self, view: TaskView) -> TimeSpent:
        """Plan, fact and the stopwatch until now."""
        watch, tracking = view.card.clocks.stopwatch, view.card.clocks.time_tracking
        elapsed = None
        if watch is not None:
            since = watch.running_since
            elapsed = watch.total_ms + (0 if since is None else ms_between(since, self._clock()))
        return TimeSpent(
            plan_minutes=None if tracking is None else tracking.plan_minutes,
            fact_minutes=None if tracking is None else tracking.fact_minutes,
            stopwatch_ms=elapsed,
            stopwatch_running=watch is not None and watch.running_since is not None,
        )


def _who(view: TaskView, context: ToolContext) -> WhoDoes | None:
    who = view.card.assignee
    if who is None:
        return None
    return WhoDoes(name=who.name, is_you=who.user_id == context.scope.user_id)


def _workspace(view: TaskView) -> WorkspaceRef | None:
    space = view.card.space
    return None if space is None else WorkspaceRef(workspace_id=space.org_id, name=space.name)


def _on_board(view: TaskView, found: Found) -> OnBoard | None:
    if view.placement is None:
        return None
    board_id, column_id = view.placement
    return OnBoard(
        board_id=board_id, board_name=found.boards.get(board_id, ""),
        column_title=found.columns.get(column_id, ""),
    )  # fmt: skip


def _board_out(board: BoardView) -> BoardRead:
    columns = [
        BoardColumnCards(
            title=column.title, kind=column.kind, more=column.more,
            cards=[
                BoardCard(
                    task_id=view.card.id, title=view.card.title, priority=view.card.priority,
                    due_on=view.card.due_on,
                    who=None if view.card.assignee is None else view.card.assignee.name,
                )
                for view in column.cards
            ],
        )
        for column in board.columns
    ]  # fmt: skip
    return BoardRead(
        board=BoardRef(board_id=board.board_id, name=board.name), columns=columns,
        other_boards=[BoardRef(board_id=b, name=n) for b, n in board.others],
    )  # fmt: skip


def agent_tools(reads: LeoReads) -> tuple[AgentTool, ...]:
    """The toolset's reads bound to their handlers."""
    handlers = TaskToolReads(reads)
    bound: tuple[ReadTool[Any, Any], ...] = (
        ReadTool(SEARCH_TASKS, handlers.search),
        ReadTool(LIST_BOARD, handlers.list_board),
    )
    return bound
