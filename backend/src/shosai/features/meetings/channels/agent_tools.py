"""Leo's `meetings` toolset bound: the person's live calls, a call started, a call ended (MR-D8).

The writes are the owner's own room routes run for Leo: checked when proposed, applied once
after approval with the item's mark (`ActionItems`, Leo §8.4). A start opens a room in the
person's Personal space, as "New meeting" does; an end closes the person's room for good and
then ends its call in the SFU, as the room's End does — the sweep ends it if the SFU does not
answer. A room the person does not own reads as not found.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from pydantic import JsonValue

from shosai.core.agent_tools.bindings import AgentTool, ReadTool, WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import (
    PlannedEffect,
    Preview,
    PreviewParam,
    ToolError,
    ToolErrorCode,
    ToolResult,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.pagination.page import PageRequest
from shosai.features.identity.contracts import Principal as Person
from shosai.features.meetings.application.room_reads import owned_room
from shosai.features.meetings.application.rooms import RoomBook, close_room, open_room
from shosai.features.meetings.application.video_server import VideoServer, VideoUnavailableError
from shosai.features.meetings.channels import agent_words as words
from shosai.features.meetings.channels.agent_specs import (
    END_CALL,
    LIST_LIVE,
    START_CALL,
    CallEnded,
    CallStarted,
    EndCall,
    LiveCall,
    LiveCalls,
    NoArguments,
    StartCall,
)
from shosai.features.meetings.domain.invites import room_link
from shosai.features.meetings.domain.principals import principal_of
from shosai.features.meetings.domain.rooms import RoomRuleError, checked_title

# Своих звонков одновременно у человека немного; модели — не больше страницы.
LIVE_SHOWN = 20


def person(context: ToolContext) -> Person:
    """The person the run acts for; a tool context always carries one."""
    if context.scope.user_id is None:
        message = "контекст инструмента без человека"
        raise ValueError(message)
    return Person(context.scope.user_id, context.scope.home, 0)


def shown(value: JsonValue) -> PreviewParam:
    """A planned value as a card's parameter: a text or a number, nothing for anything else."""
    return value if isinstance(value, str | int) else None


def refused(error: AppError) -> ToolError:
    """A refusal of the rooms as the model reads it."""
    if error.code == "room_not_found":
        return ToolError(ToolErrorCode.NOT_FOUND)
    return ToolError(ToolErrorCode.CONFLICT, {"reason": error.code})


class MeetingTools:
    """The handlers of the live calls' list, a call's start and its end."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[RoomBook, ActionItems, VideoServer],
        origin: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._book, self._items, self._server = collaborators
        self._origin = origin
        self._clock = clock

    def bound(self) -> tuple[AgentTool, ...]:
        """The list and the two writes."""
        return (
            ReadTool(LIST_LIVE, self.listed),
            WriteTool(START_CALL, self.plan_start, self.preview_start, self.start),
            WriteTool(END_CALL, self.plan_end, self.preview_end, self.end),
        )

    async def listed(self, args: NoArguments, context: ToolContext) -> ToolResult[LiveCalls]:
        """The person's Personal rooms with a call going on, with how many are in each."""
        del args
        views, _ = await self._book.live(person(context), None, PageRequest(limit=LIVE_SHOWN))
        calls = [
            LiveCall(
                room_id=view.room.id, title=view.room.title,
                invite_link=room_link(self._origin, view.invite_token),
                started_at=view.call.started_at, participants=view.call.participants,
                notes_on=view.room.notes_on,
            )
            for view in views
            if view.call is not None
        ]  # fmt: skip
        return ToolResult(LiveCalls(calls=calls))

    async def plan_start(self, args: StartCall, context: ToolContext) -> PlannedEffect | ToolError:
        """The title checked as the room page checks it."""
        del context
        try:
            title = checked_title(args.title)
        except RoomRuleError as error:
            return ToolError(ToolErrorCode.INVALID_ARGUMENTS, {"reason": error.code})
        return PlannedEffect(("personal",), {"title": title})

    async def preview_start(self, effect: PlannedEffect, context: ToolContext) -> Preview:
        """The new meeting's title, if it has one."""
        del context
        return Preview(words.START.key, {"title": shown(effect.data.get("title"))})

    async def start(
        self, effect: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[CallStarted]:
        """The room opened once for the item's key; the same room on a repeat."""
        principal, title = person(context), effect.data.get("title")

        async def opened() -> CallStarted:
            record = await open_room(
                session, principal, title if isinstance(title, str) else None, None
            )
            return CallStarted(
                room_id=record.id, invite_link=room_link(self._origin, record.invite_token),
                join_path=f"/app/meet/{record.invite_token}",
            )  # fmt: skip

        async with self._transactions.begin(principal.scope()) as session:
            made = await self._items.once(session, (key, START_CALL.name, 1), CallStarted, opened)
        return ToolResult(made)

    async def plan_end(self, args: EndCall, context: ToolContext) -> PlannedEffect | ToolError:
        """The person's open room frozen with its title and how many are in its call."""
        try:
            view = await self._book.read(person(context), args.room_id)
        except AppError as error:
            return refused(error)
        if not view.room.is_open:
            return ToolError(ToolErrorCode.CONFLICT, {"reason": "room_closed"})
        people = await self._present(view.room.lk_room_name)
        data = {"room_id": str(args.room_id), "title": view.room.title, "people": people}
        return PlannedEffect((str(args.room_id),), data, view.room.org_id)

    async def preview_end(self, effect: PlannedEffect, context: ToolContext) -> Preview:
        """The meeting's title and how many leave with it."""
        del context
        data = effect.data
        return Preview(
            words.END.key, {"title": shown(data.get("title")), "people": shown(data.get("people"))}
        )

    async def end(
        self, effect: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[CallEnded]:
        """The planned room closed once for the item's key, then its call ended in the SFU."""
        principal, room_id = person(context), UUID(str(effect.data["room_id"]))
        scope = TenancyScope(principal.home, principal.user_id, effect.org_id)
        try:
            async with self._transactions.begin(scope) as session:
                record = await owned_room(session, principal.user_id, room_id, lock=True)

                async def closed() -> CallEnded:
                    await close_room(session, record, self._clock())
                    return CallEnded()

                ended = await self._items.once(session, (key, END_CALL.name, 1), CallEnded, closed)
        except AppError as error:
            return ToolResult(error=refused(error))
        await self._book.end_in_sfu(record.lk_room_name)
        return ToolResult(ended)

    async def _present(self, lk_room_name: str) -> int | None:
        try:
            sessions = await self._server.participants(lk_room_name)
        except VideoUnavailableError:
            return None
        return sum(1 for item in sessions if principal_of(item.identity) is not None)
