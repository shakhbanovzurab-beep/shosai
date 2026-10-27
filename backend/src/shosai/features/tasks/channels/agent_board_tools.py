"""Leo's `boards` toolset bound: the list, and a board made, changed, deleted and chosen for
incoming work (Leo §8.1, §8.4).

The writes run the cabinet's own board changes (`board_edits`) through `BoardWork`: checked
when proposed, applied once after approval. A deletion's card counts the person's hand-made
tasks that go with the board; their attachments go back to files after the commit, as the
cabinet's deletion gives them.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.bindings import AgentTool, ReadTool, WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import PlannedEffect, Preview, ToolError, ToolResult
from shosai.core.i18n.locales import normalize_language
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER
from shosai.features.tasks.application.attachment_releases import AttachmentReleases
from shosai.features.tasks.application.board_access import owned_board
from shosai.features.tasks.application.board_edits import (
    board_changed,
    board_deleted,
    board_made,
    incoming_chosen,
)
from shosai.features.tasks.application.board_reads import BoardReads
from shosai.features.tasks.channels import agent_board_words as words
from shosai.features.tasks.channels.agent_board_specs import (
    CHOOSE_INCOMING,
    CREATE,
    DELETE,
    LIST,
    UPDATE,
    BoardLine,
    BoardMade,
    BoardRef,
    BoardsListed,
    ChooseIncoming,
    CreateBoard,
    Done,
    NoArguments,
    UpdateBoard,
)
from shosai.features.tasks.channels.agent_board_work import BoardWork, planned
from shosai.features.tasks.channels.agent_tool_errors import person
from shosai.features.tasks.domain.boards import checked_board_columns, checked_board_name
from shosai.features.tasks.domain.tasks import TaskSource
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    TaskPlacementRecord,
)
from shosai.features.tasks.infrastructure.task_records import TaskRecord

PLACED = TaskPlacementRecord


class BoardTools:
    """The handlers of the boards' list and of the boards' own writes."""

    def __init__(
        self,
        work: BoardWork,
        services: tuple[BoardReads, PortDirectory, AttachmentReleases],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._work = work
        self._reads, self._ports, self._releases = services
        self._clock = clock

    def bound(self) -> tuple[AgentTool, ...]:
        """The list and the four writes of boards themselves."""
        return (
            ReadTool(LIST, self.listed),
            WriteTool(CREATE, self.plan_create, self.preview_create, self.create),
            WriteTool(UPDATE, self.plan_update, self.preview_update, self.update),
            WriteTool(DELETE, self.plan_delete, self.preview_delete, self.delete),
            WriteTool(CHOOSE_INCOMING, self.plan_incoming, self.preview_incoming, self.incoming),
        )

    async def listed(self, args: NoArguments, context: ToolContext) -> ToolResult[BoardsListed]:
        """The person's boards with their open tasks and the incoming work that waits."""
        del args
        principal = person(context)
        async with self._work.transactions.begin(principal.scope(), read_only=True) as session:
            view = await self._reads.listing(session, principal.user_id, self._clock())
        boards = [
            BoardLine(
                board_id=item.id, name=item.name, icon=item.icon, incoming=item.incoming,
                open_tasks=item.task_count,
            )
            for item in view.items
        ]  # fmt: skip
        return ToolResult(BoardsListed(boards=boards, waiting_incoming=view.open_incoming))

    async def plan_create(
        self, args: CreateBoard, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """The board's name and its own columns, if given, checked."""

        async def read(_: AsyncSession) -> None:
            checked_board_name(args.name)
            if args.columns is not None:
                checked_board_columns([(column.title, column.kind) for column in args.columns])

        return await self._work.check(context, read) or planned(args, "personal")

    async def preview_create(self, effect: PlannedEffect, context: ToolContext) -> Preview:
        """The new board's name and its own columns in order."""
        del context
        args = CreateBoard.model_validate(effect.data)
        titles = None if args.columns is None else ", ".join(c.title for c in args.columns)
        return Preview(words.CREATE.key, {"name": args.name.strip(), "columns": titles})

    async def create(
        self, effect: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[BoardMade]:
        """Make the board once: its own columns, or its template's in the profile's language."""
        args = CreateBoard.model_validate(effect.data)
        viewer = person(context).user_id
        drafts = args.columns
        columns = args.template if drafts is None else [(c.title, c.kind) for c in drafts]

        async def made(session: AsyncSession) -> BoardMade:
            profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(session, viewer)
            language = None if profile is None else normalize_language(profile.language)
            board = await board_made(
                session, viewer, (args.name, args.icon, columns), (language, self._clock())
            )
            ids = await session.scalars(
                select(BoardColumnRecord.id)
                .where(BoardColumnRecord.board_id == board.id)
                .order_by(BoardColumnRecord.position)
            )
            return BoardMade(board_id=board.id, columns=list(ids))

        return await self._work.once(context, (key, CREATE.name), (BoardMade, made))

    async def plan_update(
        self, args: UpdateBoard, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """The board is the person's and the new name holds."""

        async def read(session: AsyncSession) -> None:
            await owned_board(session, person(context).user_id, args.board_id)
            if args.name is not None:
                checked_board_name(args.name)

        return await self._work.check(context, read) or planned(args, str(args.board_id))

    async def preview_update(self, effect: PlannedEffect, context: ToolContext) -> Preview:
        """The board's name now and the new one."""
        args = UpdateBoard.model_validate(effect.data)
        name = await self._work.board_name(context, args.board_id)
        new_name = None if args.name is None else args.name.strip()
        return Preview(words.UPDATE.key, {"name": name, "new_name": new_name})

    async def update(
        self, effect: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[Done]:
        """Rename the board or change its icon, once."""
        args = UpdateBoard.model_validate(effect.data)
        viewer = person(context).user_id

        async def changed(session: AsyncSession) -> Done:
            change = (args.name, args.icon, self._clock())
            await board_changed(session, viewer, args.board_id, change)
            return Done()

        return await self._work.once(context, (key, UPDATE.name), (Done, changed))

    async def plan_delete(self, args: BoardRef, context: ToolContext) -> PlannedEffect | ToolError:
        """The board is the person's."""

        async def read(session: AsyncSession) -> None:
            await owned_board(session, person(context).user_id, args.board_id)

        return await self._work.check(context, read) or planned(args, str(args.board_id))

    async def preview_delete(self, effect: PlannedEffect, context: ToolContext) -> Preview:
        """The board's name and how many of the person's hand-made tasks go with it."""
        args = BoardRef.model_validate(effect.data)
        viewer = person(context).user_id
        async with self._work.transactions.begin(
            person(context).scope(), read_only=True
        ) as session:
            board = await owned_board(session, viewer, args.board_id)
            gone = await session.scalar(
                select(func.count())
                .select_from(TaskRecord)
                .join(PLACED, PLACED.task_id == TaskRecord.id)
                .where(
                    PLACED.user_id == viewer, PLACED.board_id == args.board_id,
                    TaskRecord.user_id == viewer, TaskRecord.org_id.is_(None),
                    TaskRecord.source == TaskSource.MANUAL.value,
                )
            )  # fmt: skip
        return Preview(words.DELETE.key, {"name": board.name, "tasks": gone or 0})

    async def delete(
        self, effect: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[Done]:
        """Delete the board with its hand-made personal tasks, once; their attachments go back."""
        args = BoardRef.model_validate(effect.data)
        principal = person(context)

        async def deleted(session: AsyncSession) -> Done:
            await board_deleted(session, self._work.outbox, principal.user_id, args.board_id)
            return Done()

        result = await self._work.once(context, (key, DELETE.name), (Done, deleted))
        if result.error is None:
            await self._releases.owner(principal.scope())
        return result

    async def plan_incoming(
        self, args: ChooseIncoming, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """The board, if one is named, is the person's."""

        async def read(session: AsyncSession) -> None:
            if args.board_id is not None:
                await owned_board(session, person(context).user_id, args.board_id)

        target = "none" if args.board_id is None else str(args.board_id)
        return await self._work.check(context, read) or planned(args, target)

    async def preview_incoming(self, effect: PlannedEffect, context: ToolContext) -> Preview:
        """The board incoming work goes to, or none."""
        args = ChooseIncoming.model_validate(effect.data)
        if args.board_id is None:
            return Preview(words.NO_INCOMING.key, {})
        board = await self._work.board_name(context, args.board_id)
        return Preview(words.INCOMING.key, {"board": board})

    async def incoming(
        self, effect: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[Done]:
        """Choose the board for incoming work, once; what waits lands at once."""
        args = ChooseIncoming.model_validate(effect.data)
        viewer = person(context).user_id

        async def chosen(session: AsyncSession) -> Done:
            reading = (self._reads.readable(viewer), self._clock())
            await incoming_chosen(session, viewer, args.board_id, reading)
            return Done()

        return await self._work.once(context, (key, CHOOSE_INCOMING.name), (Done, chosen))
