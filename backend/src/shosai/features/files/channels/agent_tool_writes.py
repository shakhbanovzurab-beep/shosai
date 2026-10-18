"""The write tools of Leo's `files` toolset: Leo's switch, a move, a deletion (files step 9).

`plan` checks the target is the person's own and freezes it; `preview` names it for the
action card by an i18n key; `execute` runs only through the Action Gateway, in the
person's transaction, on the planned target alone: the access is checked again by the same
edits the File Manager's routes make, and the item key, the effect and the audit event
commit together (`ActionItems`). A refusal becomes a typed tool error.
"""

from collections.abc import Awaitable, Callable
from typing import Final
from uuid import UUID

from pydantic import BaseModel
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
from shosai.core.kernel.errors import AppError
from shosai.features.files.application.file_edits import FileChanges, FileEdits
from shosai.features.files.application.folders import Folders
from shosai.features.files.application.leo_use import LeoUse, own_folders
from shosai.features.files.channels.agent_tools import (
    DELETE,
    MOVE,
    SET_LEO_USE,
    DeletedFile,
    DeleteFile,
    FileMoved,
    LeoTarget,
    LeoUseSet,
    MoveFile,
    SetLeoUse,
)
from shosai.features.files.domain.kinds import leo_readable
from shosai.features.files.infrastructure.file_records import FileFolderRecord, StorageFileRecord
from shosai.features.identity.contracts import Principal

# Отказы срезов, которые модель понимает как «не найдено» и «сервис недоступен».
GONE: Final = frozenset({"file_not_found", "folder_not_found"})
UNAVAILABLE: Final = frozenset({"entitlements_unavailable"})

type Effect[O] = Callable[[AsyncSession], Awaitable[O]]


def person(context: ToolContext) -> Principal:
    """The person the run acts for; a tool context always carries one."""
    user_id = context.scope.user_id
    if user_id is None:
        message = "контекст инструмента без человека"
        raise ValueError(message)
    return Principal(user_id, context.scope.home, 0)


def tool_error(error: AppError) -> ToolError:
    """A slice's refusal as the closed set of tool errors the model can explain."""
    if error.code in GONE:
        return ToolError(ToolErrorCode.NOT_FOUND)
    if error.code == "leo_limit":
        limit = error.params.get("limit_bytes")
        params = {} if not isinstance(limit, int) else {"limit_bytes": limit}
        return ToolError(ToolErrorCode.LIMIT_REACHED, params)
    if error.code in UNAVAILABLE:
        return ToolError(ToolErrorCode.UNAVAILABLE)
    return ToolError(ToolErrorCode.FAILED, {"reason": error.code})


class FileWrites:
    """Plans, previews and executes the person's file writes."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[FileEdits, Folders, LeoUse, ActionItems],
    ) -> None:
        self._transactions = transactions
        self._edits, self._folders, self._leo, self._items = services

    def bound(
        self,
    ) -> tuple[
        WriteTool[SetLeoUse, LeoUseSet],
        WriteTool[MoveFile, FileMoved],
        WriteTool[DeleteFile, DeletedFile],
    ]:
        """The three write tools."""
        return (
            WriteTool(SET_LEO_USE, self.plan_leo_use, self.preview_leo_use, self.execute_leo_use),
            WriteTool(MOVE, self.plan_move, self.preview_move, self.execute_move),
            WriteTool(DELETE, self.plan_delete, self.preview_delete, self.execute_delete),
        )

    async def plan_leo_use(
        self, arguments: SetLeoUse, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the file or the folder whose switch changes."""
        if arguments.folder_id is not None:
            if await self._folder(context, arguments.folder_id) is None:
                return ToolError(ToolErrorCode.NOT_FOUND)
            target, target_id = LeoTarget.FOLDER, arguments.folder_id
        else:
            found = (
                None if arguments.file_id is None else await self._file(context, arguments.file_id)
            )
            if found is None or arguments.file_id is None:
                return ToolError(ToolErrorCode.NOT_FOUND)
            name, size = found
            if arguments.use and not leo_readable(name, size):
                return ToolError(ToolErrorCode.FAILED, {"reason": "leo_unreadable"})
            target, target_id = LeoTarget.FILE, arguments.file_id
        return PlannedEffect((str(target_id),), {"target": target.value, "use": arguments.use})

    async def preview_leo_use(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: which file or folder, switched on or off."""
        target, target_id = LeoTarget(str(planned.data["target"])), UUID(planned.targets[0])
        params = {"target": target.value, "use": bool(planned.data["use"])}
        name = await self._name(context, target, target_id)
        return Preview("agent.files.set_leo_use", {**params, "name": name})

    async def execute_leo_use(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[LeoUseSet]:
        """Switch Leo's use of the planned file or folder only."""
        principal = person(context)
        target, target_id = LeoTarget(str(planned.data["target"])), UUID(planned.targets[0])
        use = bool(planned.data["use"])
        try:
            limit = await self._leo.limit(principal) if use else None
        except AppError as error:
            return ToolResult(error=tool_error(error))

        async def effect(session: AsyncSession) -> LeoUseSet:
            if target is LeoTarget.FILE:
                changes = FileChanges(leo=use)
                await self._edits.edit(session, principal, (target_id, changes), limit)
            else:
                await self._folders.change(session, principal, (target_id, None, use), limit)
            return LeoUseSet(target=target, target_id=target_id, use=use)

        return await self._apply(context, (key, SET_LEO_USE.name), LeoUseSet, effect)

    async def plan_move(
        self, arguments: MoveFile, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the file and the folder it goes into."""
        if await self._file(context, arguments.file_id) is None:
            return ToolError(ToolErrorCode.NOT_FOUND)
        folder_id = arguments.folder_id
        if folder_id is not None and await self._folder(context, folder_id) is None:
            return ToolError(ToolErrorCode.NOT_FOUND)
        folder = None if folder_id is None else str(folder_id)
        return PlannedEffect((str(arguments.file_id),), {"folder_id": folder})

    async def preview_move(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: which file, into which folder or the root."""
        name = await self._name(context, LeoTarget.FILE, UUID(planned.targets[0]))
        raw = planned.data["folder_id"]
        folder = (
            None if raw is None else await self._name(context, LeoTarget.FOLDER, UUID(str(raw)))
        )
        return Preview("agent.files.move", {"name": name, "folder": folder})

    async def execute_move(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[FileMoved]:
        """Move the planned file into the planned folder only."""
        principal = person(context)
        file_id, raw = UUID(planned.targets[0]), planned.data["folder_id"]
        folder_id = None if raw is None else UUID(str(raw))
        try:
            limit = await self._leo.limit(principal)
        except AppError as error:
            return ToolResult(error=tool_error(error))

        async def effect(session: AsyncSession) -> FileMoved:
            changes = FileChanges(move=True, folder_id=folder_id)
            await self._edits.edit(session, principal, (file_id, changes), limit)
            return FileMoved(file_id=file_id, folder_id=folder_id)

        return await self._apply(context, (key, MOVE.name), FileMoved, effect)

    async def plan_delete(
        self, arguments: DeleteFile, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the file to delete."""
        if await self._file(context, arguments.file_id) is None:
            return ToolError(ToolErrorCode.NOT_FOUND)
        return PlannedEffect((str(arguments.file_id),))

    async def preview_delete(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: which file goes."""
        name = await self._name(context, LeoTarget.FILE, UUID(planned.targets[0]))
        return Preview("agent.files.delete", {"name": name})

    async def execute_delete(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[DeletedFile]:
        """Delete the planned file only."""
        principal = person(context)
        file_id = UUID(planned.targets[0])

        async def effect(session: AsyncSession) -> DeletedFile:
            await self._edits.remove(session, principal, file_id)
            return DeletedFile(file_id=file_id)

        return await self._apply(context, (key, DELETE.name), DeletedFile, effect)

    async def _apply[O: BaseModel](
        self, context: ToolContext, item: tuple[str, str], output: type[O], effect: Effect[O]
    ) -> ToolResult[O]:
        """The effect once per item key, in the person's transaction, or its tool error."""
        key, tool = item
        try:
            async with self._transactions.begin(context.scope) as session:
                outcome = await self._items.once(
                    session, (key, tool, 1), output, lambda: effect(session)
                )
        except AppError as error:
            return ToolResult(error=tool_error(error))
        return ToolResult(outcome)

    async def _file(self, context: ToolContext, file_id: UUID) -> tuple[str, int] | None:
        """The name and size of one of the person's own files, or None."""
        query = self._edits.own_files(person(context)).where(StorageFileRecord.id == file_id)
        async with self._transactions.begin(context.scope, read_only=True) as session:
            record = await session.scalar(query)
            return None if record is None else (record.name, record.size_bytes)

    async def _folder(self, context: ToolContext, folder_id: UUID) -> str | None:
        """The name of one of the person's folders, or None."""
        user_id = person(context).user_id
        query = own_folders(user_id).where(FileFolderRecord.id == folder_id)
        async with self._transactions.begin(context.scope, read_only=True) as session:
            record = await session.scalar(query)
            return None if record is None else record.name

    async def _name(self, context: ToolContext, target: LeoTarget, target_id: UUID) -> str | None:
        """The name the card shows; None when the target went since the plan."""
        if target is LeoTarget.FOLDER:
            return await self._folder(context, target_id)
        found = await self._file(context, target_id)
        return None if found is None else found[0]
