"""The write tools of Leo's `notes` toolset: a folder and a new write-up (step 16).

`plan` reads the meeting the person may manage and freezes the target and what changes;
`preview` names them for the action card by an i18n key; `execute` runs only through the
Action Gateway, in the meeting's own scope, on the planned meeting alone: access is checked
again by the same services the cabinet's routes use, and the item key, the effect and the
audit event commit together (`ActionItems`). A refusal becomes a typed tool error. The
share link's two tools are in `agent_link_writes`.
"""

from collections.abc import Awaitable, Callable
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.bindings import WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import (
    PlannedEffect,
    Preview,
    ToolError,
    ToolErrorCode,
    ToolResult,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.idempotency.ledger import account_key
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.notes.application.library import MeetingLibrary
from shosai.features.notes.application.visibility import meeting_for, meeting_scope
from shosai.features.notes.application.write_up_layout import layout_of
from shosai.features.notes.application.write_up_rewrites import RewriteRequest, WriteUpRewrites
from shosai.features.notes.channels.agent_write_tools import (
    MOVE_TO_FOLDER,
    REGENERATE_NOTES,
    MovedToFolder,
    MoveToFolder,
    NotesRegenerating,
    RegenerateNotes,
)
from shosai.features.notes.domain.reading import filing_refusal
from shosai.features.notes.domain.templates import ENHANCED, builtin
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.notes_records import (
    FolderRecord,
    NotesRecord,
    TemplateRecord,
)
from shosai.features.workspaces.contracts import ACCESS_POLICY

# Отказы среза, которые модель понимает как «не найдено» и «нет прав».
GONE: Final = frozenset({"meeting_not_found", "folder_not_found", "template_not_found"})
REFUSED: Final = frozenset(
    {
        "meeting_read_only",
        "meeting_not_yours",
        "company_meeting_has_no_folder",
        "template_not_shipped",
    }
)

type Effect[O] = Callable[[AsyncSession], Awaitable[O]]


def person(context: ToolContext) -> Principal:
    """The person the run acts for; a tool context always carries one."""
    user_id = context.scope.user_id
    if user_id is None:
        message = "контекст инструмента без человека"
        raise ValueError(message)
    return Principal(user_id, context.scope.home, 0)


def tool_error(error: AppError) -> ToolError:
    """A refusal of the slice as the closed set of tool errors the model can explain."""
    if error.code in GONE:
        return ToolError(ToolErrorCode.NOT_FOUND)
    if error.code in REFUSED:
        return ToolError(ToolErrorCode.FORBIDDEN, {"reason": error.code})
    return ToolError(ToolErrorCode.FAILED, {"reason": error.code})


class WriteSteps:
    """What every write tool of the slice shares: the meeting's read and the applied item."""

    def __init__(
        self, transactions: HomeTransactions, collaborators: tuple[PortDirectory, ActionItems]
    ) -> None:
        self.transactions = transactions
        self.ports, self._items = collaborators

    async def managed(
        self, session: AsyncSession, context: ToolContext, meeting_id: UUID
    ) -> MeetingRecord | ToolError:
        """The meeting if the person may manage it, else the tool error."""
        policy = self.ports.get(ACCESS_POLICY)
        try:
            meeting, manageable = await meeting_for(
                session, policy, person(context).user_id, meeting_id
            )
        except AppError as error:
            return tool_error(error)
        if not manageable:
            return ToolError(ToolErrorCode.FORBIDDEN, {"reason": "meeting_read_only"})
        return meeting

    async def scope_of(self, context: ToolContext, meeting_id: UUID) -> TenancyScope:
        """The scope the meeting changes in; `MeetingNotFoundError` once it is gone."""
        policy = self.ports.get(ACCESS_POLICY)
        async with self.transactions.begin(context.scope, read_only=True) as session:
            return await meeting_scope(session, policy, context.scope, meeting_id)

    async def apply[O: BaseModel](
        self, scope: TenancyScope, item: tuple[str, str], output: type[O], effect: Effect[O]
    ) -> ToolResult[O]:
        """The effect once per item key, in the meeting's transaction, or its tool error."""
        key, tool = item
        try:
            async with self.transactions.begin(scope) as session:
                outcome = await self._items.once(
                    session, (key, tool, 1), output, lambda: effect(session)
                )
        except AppError as error:
            return ToolResult(error=tool_error(error))
        return ToolResult(outcome)

    async def title(self, context: ToolContext, meeting_id: UUID) -> str | None:
        """The title the card shows; None once the meeting cannot be read."""
        async with self.transactions.begin(context.scope, read_only=True) as session:
            found = await self.managed(session, context, meeting_id)
        return None if isinstance(found, ToolError) else found.title


class NoteWrites:
    """Plans, previews and executes filing a meeting and rewriting its notes."""

    def __init__(self, steps: WriteSteps, services: tuple[MeetingLibrary, WriteUpRewrites]) -> None:
        self._steps = steps
        self._library, self._rewrites = services

    def bound(
        self,
    ) -> tuple[
        WriteTool[MoveToFolder, MovedToFolder], WriteTool[RegenerateNotes, NotesRegenerating]
    ]:
        """The two write tools."""
        return (
            WriteTool(MOVE_TO_FOLDER, self.plan_move, self.preview_move, self.execute_move),
            WriteTool(
                REGENERATE_NOTES, self.plan_regenerate, self.preview_regenerate,
                self.execute_regenerate,
            ),
        )  # fmt: skip

    async def plan_move(
        self, arguments: MoveToFolder, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the meeting and the folder it goes into, found by its name."""
        user_id = person(context).user_id
        async with self._steps.transactions.begin(context.scope, read_only=True) as session:
            meeting = await self._steps.managed(session, context, arguments.meeting_id)
            if isinstance(meeting, ToolError):
                return meeting
            refusal = filing_refusal(
                owner=meeting.user_id == user_id, company=meeting.org_id is not None
            )
            if refusal is not None:
                return ToolError(ToolErrorCode.FORBIDDEN, {"reason": refusal.value})
            folder: UUID | ToolError | None = None
            if arguments.folder is not None:
                folder = await folder_named(session, user_id, arguments.folder)
        if isinstance(folder, ToolError):
            return folder
        planned = None if folder is None else str(folder)
        return PlannedEffect((str(meeting.id),), {"folder_id": planned})

    async def preview_move(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: which meeting, into which folder or out of its folder."""
        raw = planned.data["folder_id"]
        folder = None
        if raw is not None:
            async with self._steps.transactions.begin(context.scope, read_only=True) as session:
                record = await session.get(FolderRecord, UUID(str(raw)))
                folder = None if record is None else record.name
        title = await self._steps.title(context, UUID(planned.targets[0]))
        return Preview("agent.notes.move_to_folder", {"title": title, "folder": folder})

    async def execute_move(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[MovedToFolder]:
        """File the planned meeting in the planned folder only."""
        principal, meeting_id = person(context), UUID(planned.targets[0])
        raw = planned.data["folder_id"]
        folder_id = None if raw is None else UUID(str(raw))

        async def effect(session: AsyncSession) -> MovedToFolder:
            await self._library.file_in(session, principal, meeting_id, folder_id)
            folder = None if folder_id is None else await session.get(FolderRecord, folder_id)
            name = None if folder is None else folder.name
            return MovedToFolder(meeting_id=meeting_id, folder=name)

        try:
            scope = await self._steps.scope_of(context, meeting_id)
        except AppError as error:
            return ToolResult(error=tool_error(error))
        return await self._steps.apply(scope, (key, MOVE_TO_FOLDER.name), MovedToFolder, effect)

    async def plan_regenerate(
        self, arguments: RegenerateNotes, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the meeting and the template its new write-up follows."""
        async with self._steps.transactions.begin(context.scope, read_only=True) as session:
            meeting = await self._steps.managed(session, context, arguments.meeting_id)
            if isinstance(meeting, ToolError):
                return meeting
            notes = await session.get(NotesRecord, meeting.id)
            if notes is None or notes.write_up is None:
                return ToolError(ToolErrorCode.FAILED, {"reason": "notes_not_ready"})
            chosen = arguments.template
            template = chosen.value if chosen is not None else meeting.template_id or ENHANCED
            if await layout_of(session, template) is None:
                return ToolError(ToolErrorCode.NOT_FOUND)
        return PlannedEffect((str(meeting.id),), {"template_id": template})

    async def preview_regenerate(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: which meeting, by which template — a shipped code or the person's name."""
        template = str(planned.data["template_id"])
        shipped = builtin(template) is not None
        name = template
        if not shipped:
            async with self._steps.transactions.begin(context.scope, read_only=True) as session:
                own = await session.scalar(
                    select(TemplateRecord.name).where(TemplateRecord.id == UUID(template))
                )
            name = own or ""
        title = await self._steps.title(context, UUID(planned.targets[0]))
        params = {"title": title, "template": name, "shipped": shipped}
        return Preview("agent.notes.regenerate_notes", params)

    async def execute_regenerate(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[NotesRegenerating]:
        """Start the rewrite of the planned meeting by the planned template only."""
        principal, meeting_id = person(context), UUID(planned.targets[0])
        request = RewriteRequest(
            meeting_id=meeting_id, template_id=str(planned.data["template_id"])
        )
        try:
            scope, layout = await self._rewrites.prepare(principal, request)
        except AppError as error:
            return ToolResult(error=tool_error(error))
        rewrite_key = account_key(principal.user_id, key)

        async def effect(session: AsyncSession) -> NotesRegenerating:
            accepted = await self._rewrites.start_in(
                session, principal, (request, layout), rewrite_key
            )
            return NotesRegenerating(meeting_id=meeting_id, run_id=accepted.run_id)

        result = await self._steps.apply(
            scope, (key, REGENERATE_NOTES.name), NotesRegenerating, effect
        )
        if result.output is not None:
            # Повтор ключа шлёт стадию ещё раз: движок пропускает законченную стадию.
            await self._rewrites.kick(scope, meeting_id, result.output.run_id)
        return result


async def folder_named(session: AsyncSession, user_id: UUID, name: str) -> UUID | ToolError:
    """The person's one folder of that name, whatever its case; a tool error otherwise."""
    wanted = name.strip().casefold()
    rows = await session.execute(
        select(FolderRecord.id, FolderRecord.name).where(FolderRecord.user_id == user_id)
    )
    found = [folder_id for folder_id, folder in rows if folder.strip().casefold() == wanted]
    if not found:
        return ToolError(ToolErrorCode.NOT_FOUND)
    if len(found) > 1:
        return ToolError(ToolErrorCode.FAILED, {"reason": "folder_ambiguous"})
    return found[0]
