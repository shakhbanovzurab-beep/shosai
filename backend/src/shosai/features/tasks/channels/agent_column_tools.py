"""Leo's `boards` toolset bound, its columns: one added, changed or removed (Leo §8.1, §8.4).

The writes run the cabinet's own column changes (`columns`) through `BoardWork`: checked when
proposed — the board and the column are the person's, the title holds, a board keeps room
and a column of every kind — and applied once after approval. A removed column's card names
the column its cards go to, the next one of its kind.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.bindings import AgentTool, WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import PlannedEffect, Preview, ToolError, ToolResult
from shosai.features.tasks.application.columns import (
    ColumnChange,
    NewColumn,
    column_added,
    column_changed,
    column_removed,
)
from shosai.features.tasks.channels import agent_board_words as words
from shosai.features.tasks.channels.agent_board_specs import (
    ADD_COLUMN,
    DELETE_COLUMN,
    UPDATE_COLUMN,
    AddColumn,
    ColumnMade,
    ColumnRef,
    Done,
    UpdateColumn,
)
from shosai.features.tasks.channels.agent_board_work import (
    BoardWork,
    column_in,
    columns_of,
    planned,
)
from shosai.features.tasks.channels.agent_tool_errors import person
from shosai.features.tasks.domain.boards import (
    BoardRule,
    BoardRuleError,
    check_column_room,
    checked_column_title,
)
from shosai.features.tasks.infrastructure.board_records import BoardColumnRecord


def heir_of(
    columns: list[BoardColumnRecord], column: BoardColumnRecord
) -> BoardColumnRecord | None:
    """The column a removed one's cards go to: the next of its kind; none for the last."""
    return next((c for c in columns if c.id != column.id and c.kind == column.kind), None)


class ColumnTools:
    """The handlers of the columns' writes."""

    def __init__(
        self, work: BoardWork, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._work = work
        self._clock = clock

    def bound(self) -> tuple[AgentTool, ...]:
        """The three writes of a board's columns."""
        return (
            WriteTool(ADD_COLUMN, self.plan_add, self.preview_add, self.add),
            WriteTool(UPDATE_COLUMN, self.plan_update, self.preview_update, self.update),
            WriteTool(DELETE_COLUMN, self.plan_delete, self.preview_delete, self.delete),
        )

    async def plan_add(self, args: AddColumn, context: ToolContext) -> PlannedEffect | ToolError:
        """The board is the person's, has room, and the title holds."""

        async def read(session: AsyncSession) -> None:
            checked_column_title(args.title)
            _, columns = await columns_of(session, person(context).user_id, args.board_id)
            check_column_room(len(columns))

        return await self._work.check(context, read) or planned(args, str(args.board_id))

    async def preview_add(self, effect: PlannedEffect, context: ToolContext) -> Preview:
        """The new column's title, its board and the status it shows."""
        args = AddColumn.model_validate(effect.data)
        board = await self._work.board_name(context, args.board_id)
        params = {"title": args.title.strip(), "board": board, "kind": args.kind.value}
        return Preview(words.ADD_COLUMN.key, params)

    async def add(
        self, effect: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[ColumnMade]:
        """Add the column at its position, once."""
        args = AddColumn.model_validate(effect.data)
        viewer = person(context).user_id
        new = NewColumn(args.title, args.kind, args.position, args.color)

        async def added(session: AsyncSession) -> ColumnMade:
            column = await column_added(session, viewer, (args.board_id, new), self._clock())
            return ColumnMade(column_id=column.id)

        return await self._work.once(context, (key, ADD_COLUMN.name), (ColumnMade, added))

    async def plan_update(
        self, args: UpdateColumn, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """The column is one of the person's board's, and a new title holds."""

        async def read(session: AsyncSession) -> None:
            if args.title is not None:
                checked_column_title(args.title)
            _, columns = await columns_of(session, person(context).user_id, args.board_id)
            column_in(columns, args.column_id)

        return await self._work.check(context, read) or planned(args, str(args.column_id))

    async def preview_update(self, effect: PlannedEffect, context: ToolContext) -> Preview:
        """The column's title now, its board and the new title."""
        args = UpdateColumn.model_validate(effect.data)
        board, columns = await self._work.columns(context, args.board_id)
        column = column_in(columns, args.column_id)
        new_title = None if args.title is None else args.title.strip()
        params = {"title": column.title, "board": board, "new_title": new_title}
        return Preview(words.UPDATE_COLUMN.key, params)

    async def update(
        self, effect: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[Done]:
        """Rename, move, recolour or collapse the column, once; a colour sent as null goes."""
        args = UpdateColumn.model_validate(effect.data)
        viewer = person(context).user_id
        change = ColumnChange(
            title=args.title, color=args.color, color_sent="color" in args.model_fields_set,
            collapsed=args.collapsed, position=args.position,
        )  # fmt: skip

        async def changed(session: AsyncSession) -> Done:
            changing = (args.board_id, args.column_id, change)
            await column_changed(session, viewer, changing, self._clock())
            return Done()

        return await self._work.once(context, (key, UPDATE_COLUMN.name), (Done, changed))

    async def plan_delete(self, args: ColumnRef, context: ToolContext) -> PlannedEffect | ToolError:
        """The column is one of the person's board's and not the last of its kind."""

        async def read(session: AsyncSession) -> None:
            _, columns = await columns_of(session, person(context).user_id, args.board_id)
            if heir_of(columns, column_in(columns, args.column_id)) is None:
                raise BoardRuleError(BoardRule.LAST_COLUMN_OF_KIND)

        return await self._work.check(context, read) or planned(args, str(args.column_id))

    async def preview_delete(self, effect: PlannedEffect, context: ToolContext) -> Preview:
        """The column's title, its board and the column its cards go to."""
        args = ColumnRef.model_validate(effect.data)
        board, columns = await self._work.columns(context, args.board_id)
        column = column_in(columns, args.column_id)
        heir = heir_of(columns, column)
        moved_to = None if heir is None else heir.title
        params = {"title": column.title, "board": board, "moved_to": moved_to}
        return Preview(words.DELETE_COLUMN.key, params)

    async def delete(
        self, effect: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[Done]:
        """Remove the column, once; its cards go on top of the next column of its kind."""
        args = ColumnRef.model_validate(effect.data)
        viewer = person(context).user_id

        async def removed(session: AsyncSession) -> Done:
            await column_removed(session, viewer, (args.board_id, args.column_id), self._clock())
            return Done()

        return await self._work.once(context, (key, DELETE_COLUMN.name), (Done, removed))
