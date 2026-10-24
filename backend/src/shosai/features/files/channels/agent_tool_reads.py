"""The read tools of Leo's `files` toolset: the search and the digest (files step 9).

Both act for the person of the tool context's scope, never for an id the model names, and
see exactly what `visible_files` admits. Each names the files it read as the sources of Leo's
answer, in their workspace, and labels their text: the person's own when they uploaded every
file shown, a colleague's otherwise (Leo §7.4). The digest goes through `FileReader`, as every
other slice reads a file: its facts in a short transaction, then at most 16 KiB of a
plain-text file's bytes from the home's bucket, after that transaction ends.
"""

import codecs
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.bindings import ReadTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import ToolErrorCode, ToolResult
from shosai.core.agent_tools.sources import QUOTE_MAX, TITLE_MAX, SourceKind, SourceRef
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.errors import ObjectNotFoundError
from shosai.features.files.application.file_reader import FilesReader
from shosai.features.files.application.leo_use import leo_folders, own_folders
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.channels.agent_tools import (
    READ,
    SEARCH,
    ExcerptGap,
    FileDigest,
    FoundFile,
    FoundFiles,
    ReadFile,
    SearchFiles,
)
from shosai.features.files.contracts import FileFacts, FileUnreadableError
from shosai.features.files.domain.kinds import kind_of, leo_readable, plain_text
from shosai.features.files.domain.leo import leo_use
from shosai.features.files.infrastructure.file_records import FILE_RESOURCE, StorageFileRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

# Сколько байт текстового файла читает инструмент и сколько символов отдаёт модели.
EXCERPT_BYTES: Final = 16 * 1024
EXCERPT_CHARS: Final = 6_000


class FileReads:
    """The search and the digest over the files the person may read."""

    def __init__(
        self, transactions: HomeTransactions, services: tuple[PortDirectory, FilesReader]
    ) -> None:
        self._transactions = transactions
        self._ports, self._reader = services

    def bound(self) -> tuple[ReadTool[SearchFiles, FoundFiles], ReadTool[ReadFile, FileDigest]]:
        """The two read tools."""
        return (ReadTool(SEARCH, self.search), ReadTool(READ, self.read))

    async def search(self, arguments: SearchFiles, context: ToolContext) -> ToolResult[FoundFiles]:
        """Files whose names contain the query, newest first."""
        user_id = context.scope.user_id
        if user_id is None:
            return ToolResult.failed(ToolErrorCode.FORBIDDEN)
        files = StorageFileRecord
        query = (
            visible_files(self._ports.get(ACCESS_POLICY), Viewer(user_id))
            .where(files.name.icontains(arguments.query, autoescape=True))
            .order_by(files.modified_at.desc(), files.id)
            .limit(arguments.limit + 1)
        )
        async with self._transactions.begin(context.scope, read_only=True) as session:
            found = list(await session.scalars(query))
            in_leo = leo_folders(list(await session.scalars(own_folders(user_id))))
            shown = found[: arguments.limit]
            spaces = await self._spaces(
                session, user_id, [(r.id, r.user_id, r.org_id) for r in shown]
            )
        items = [found_file(r, user_id, in_leo) for r in shown]
        return ToolResult(
            FoundFiles(files=items, more=len(found) > arguments.limit),
            sources=tuple(file_source(r.id, r.name, spaces[r.id]) for r in shown),
            provenance=label_of([r.user_id for r in shown], user_id),
        )

    async def read(self, arguments: ReadFile, context: ToolContext) -> ToolResult[FileDigest]:
        """A readable file's facts and, for plain text, the start of its text."""
        user_id = context.scope.user_id
        if user_id is None:
            return ToolResult.failed(ToolErrorCode.FORBIDDEN)
        viewer = Viewer(user_id)
        async with self._transactions.begin(context.scope, read_only=True) as session:
            found = await self._reader.facts(session, viewer, [arguments.file_id])
            facts = found.get(arguments.file_id)
            if facts is None:
                return ToolResult.failed(ToolErrorCode.NOT_FOUND)
            where = (facts.file_id, facts.owner_id, facts.org_id)
            space = (await self._spaces(session, user_id, [where]))[facts.file_id]
        label = label_of([facts.owner_id], user_id)
        if not plain_text(facts.name):
            source = file_source(facts.file_id, facts.name, space)
            return ToolResult(
                digest(facts, None, ExcerptGap.NOT_TEXT), sources=(source,), provenance=label
            )
        try:
            head = await self._head(context.scope.home, viewer, facts.file_id)
        except FileUnreadableError, ObjectNotFoundError:
            return ToolResult.failed(ToolErrorCode.NOT_FOUND)
        read = digest(facts, head, None)
        source = file_source(facts.file_id, facts.name, space, read.excerpt or "")
        return ToolResult(read, sources=(source,), provenance=label)

    async def _spaces(
        self,
        session: AsyncSession,
        user_id: UUID,
        files: list[tuple[UUID, UUID | None, UUID | None]],
    ) -> dict[UUID, UUID | None]:
        """Each file's space for Leo: its workspace, or the one a colleague's personal file is
        shared to the person through; None for the person's own."""
        spaces = {file_id: org_id for file_id, _, org_id in files}
        shared = [
            file_id for file_id, owner, org_id in files if org_id is None and owner != user_id
        ]
        if shared:
            policy = self._ports.get(ACCESS_POLICY)
            spaces |= await policy.shared_into(session, FILE_RESOURCE, shared, Viewer(user_id))
        return spaces

    async def _head(self, home: Home, viewer: Viewer, file_id: UUID) -> bytes:
        """At most `EXCERPT_BYTES` of the file's bytes, through `FileReader`."""
        head = b""
        async with self._reader.open(home, viewer, file_id) as stream:
            async for chunk in stream.chunks(EXCERPT_BYTES):
                head += chunk
                if len(head) >= EXCERPT_BYTES:
                    break
        return head[:EXCERPT_BYTES]


def file_source(file_id: UUID, name: str, org_id: UUID | None, quote: str = "") -> SourceRef:
    """A file as a source of Leo's answer, in its workspace, with the start of its text."""
    return SourceRef(
        kind=SourceKind.FILE, id=str(file_id), title=name[:TITLE_MAX], org_id=org_id,
        quote=quote[:QUOTE_MAX],
    )  # fmt: skip


def label_of(owners: list[UUID | None], user_id: UUID) -> Provenance:
    """The label of the files' text: the person's own when they uploaded all of it."""
    return Provenance.FILE_OWN if owners and set(owners) == {user_id} else Provenance.FILE_FOREIGN


def found_file(record: StorageFileRecord, user_id: UUID, in_leo: frozenset[UUID]) -> FoundFile:
    """A search hit; the folder and Leo's use only for the person's own file."""
    owned = record.user_id == user_id and record.org_id is None
    via = leo_use(
        readable=leo_readable(record.name, record.size_bytes),
        own=record.leo_on,
        folder=record.folder_id is not None and record.folder_id in in_leo,
        held=record.leo_held,
    )
    return FoundFile(
        file_id=record.id, name=record.name, kind=kind_of(record.name),
        size_bytes=record.size_bytes, modified_at=record.modified_at, owned=owned,
        folder_id=record.folder_id if owned else None, leo=via if owned else None,
    )  # fmt: skip


def digest(facts: FileFacts, head: bytes | None, gap: ExcerptGap | None) -> FileDigest:
    """The digest of a file from its facts and the first bytes read, if any."""
    excerpt, truncated = None, False
    if head is not None:
        # Неполный последний символ отбрасывается, а не превращается в замену.
        text = codecs.getincrementaldecoder("utf-8")(errors="replace").decode(head, final=False)
        excerpt = text[:EXCERPT_CHARS]
        truncated = facts.size_bytes > len(head) or len(text) > EXCERPT_CHARS
    return FileDigest(
        file_id=facts.file_id, name=facts.name, kind=facts.kind,
        content_type=facts.content_type, size_bytes=facts.size_bytes,
        leo_readable=facts.leo_readable, excerpt=excerpt, excerpt_truncated=truncated,
        no_excerpt=gap,
    )  # fmt: skip
