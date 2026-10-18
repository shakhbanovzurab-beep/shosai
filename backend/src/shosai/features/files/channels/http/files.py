"""The person's File Manager (`/v1/files*`), in the cabinet's contract (`contract.ts`).

Uploads come in as ids of ready uploads (FL-D1). A deletion is final for the person and
hidden for 7 days on the server (FL-D5). A download answers a link on Shosai's address
(FL-D9). `leo` on files and folders switches Leo's use, within the plan's knowledge limit.
A file shared in a workspace can be handed over to it (step 8a). Errors use the platform's
envelope: `file_not_found`, `folder_not_found`, `upload_count`, `upload_not_claimable`,
`storage_limit`, `name_*`, `leo_limit` (with `limit_bytes`), `leo_unreadable`,
`leo_not_used`, `entitlements_unavailable`, `share_first`, `workspace_not_found`,
`workspace_suspended`.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.application.downloads import Downloads
from shosai.features.files.application.file_edits import FileChanges
from shosai.features.files.application.file_manager import FileManager
from shosai.features.files.application.file_transfer import FileTransfers
from shosai.features.files.application.file_views import FileView, FolderView
from shosai.features.files.application.folders import Folders
from shosai.features.files.contracts import IndexStage
from shosai.features.files.domain.kinds import FileKind
from shosai.features.files.domain.leo import LeoVia
from shosai.features.files.domain.names import NameRuleError, checked_name
from shosai.features.files.domain.purposes import FILES_PER_REQUEST
from shosai.features.identity.contracts import Principal, bearer_principal


class Strict(BaseModel):
    """A request body: unknown fields are refused."""

    model_config = ConfigDict(extra="forbid")


class LeoUseOut(BaseModel):
    """How Leo uses a file and how far its indexing got."""

    via: LeoVia
    status: IndexStage
    progress: int
    chunk_count: int | None
    error: str | None


class FileItem(BaseModel):
    """A file of the File Manager."""

    id: UUID
    name: str
    kind: FileKind
    content_type: str
    size_bytes: int
    folder_id: UUID | None
    modified_at: datetime
    starred: bool
    leo_readable: bool
    leo: LeoUseOut | None


class FileFolder(BaseModel):
    """A flat folder."""

    id: UUID
    name: str
    updated_at: datetime
    leo: bool


class FilesResponse(BaseModel):
    """The person's folders and files, newest first."""

    folders: list[FileFolder]
    files: list[FileItem]


class UploadResponse(BaseModel):
    """The files made from ready uploads."""

    files: list[FileItem]


class RegisterBody(Strict):
    """Ready uploads to turn into files, where to put them, and whether Leo uses them."""

    upload_ids: Annotated[list[UUID], Field(min_length=1, max_length=FILES_PER_REQUEST)]
    folder_id: UUID | None = None
    leo: bool = False


class FileUpdate(Strict):
    """What the owner changes; `folder_id: null` moves to the root, `leo` is the file's own
    switch (a file in a folder Leo reads is used either way)."""

    name: str | None = None
    folder_id: UUID | None = None
    starred: bool | None = None
    leo: bool | None = None


class CopyBody(Strict):
    """The copy's name; a numbered name of the source when left out."""

    name: str | None = None


class FileTransferBody(Strict):
    """The workspace the file is handed over to; the person shared it there first."""

    workspace_id: UUID


class FolderBody(Strict):
    """A folder's name."""

    name: str


class FolderUpdate(Strict):
    """A folder's new name, and whether Leo uses every readable file in it."""

    name: str | None = None
    leo: bool | None = None


class DownloadOut(BaseModel):
    """Where the browser fetches the bytes, for 15 minutes."""

    url: str
    expires_at: datetime


def item_of(view: FileView) -> FileItem:
    """The contract's file."""
    leo = None if view.leo is None else LeoUseOut(
        via=view.leo.via, status=view.leo.state.stage, progress=view.leo.state.progress,
        chunk_count=view.leo.state.chunk_count, error=view.leo.state.error,
    )  # fmt: skip
    return FileItem(
        id=view.id, name=view.name, kind=view.kind, content_type=view.content_type,
        size_bytes=view.size_bytes, folder_id=view.folder_id, modified_at=view.modified_at,
        starred=view.starred, leo_readable=view.leo_readable, leo=leo,
    )  # fmt: skip


def folder_of(view: FolderView) -> FileFolder:
    """The contract's folder."""
    return FileFolder(id=view.id, name=view.name, updated_at=view.updated_at, leo=view.leo)


def valid_name(raw: str) -> str:
    """A name by the cabinet's rules, or the 422 of the rule it breaks."""
    try:
        return checked_name(raw)
    except NameRuleError as error:
        raise AppError(error.code, HTTPStatus.UNPROCESSABLE_CONTENT) from error


def named(raw: str | None) -> str | None:
    """A name given or not; a given one follows the rules."""
    return None if raw is None else valid_name(raw)


def build_files_router(
    services: tuple[FileManager, Downloads, FileTransfers], ports: PortDirectory
) -> APIRouter:
    """The person's file routes."""
    manager, downloads, transfers = services
    router = APIRouter(prefix="/v1/files", tags=["files"])
    signed_in = bearer_principal(ports)

    @router.get("")
    async def list_files(principal: Annotated[Principal, Depends(signed_in)]) -> FilesResponse:
        """The person's folders by name and files newest first."""
        found_folders, found_files = await manager.listing(principal)
        return FilesResponse(
            folders=[folder_of(f) for f in found_folders], files=[item_of(f) for f in found_files]
        )

    @router.post("", status_code=HTTPStatus.CREATED)
    async def register_files(
        principal: Annotated[Principal, Depends(signed_in)], body: RegisterBody
    ) -> UploadResponse:
        """Turn ready uploads into files; a repeat answers the same files."""
        views = await manager.register(principal, body.upload_ids, body.folder_id, leo=body.leo)
        return UploadResponse(files=[item_of(view) for view in views])

    @router.patch("/{file_id}")
    async def update_file(
        principal: Annotated[Principal, Depends(signed_in)], file_id: UUID, body: FileUpdate
    ) -> FileItem:
        """Rename, move, star a file or switch Leo's use of it."""
        changes = FileChanges(
            name=named(body.name), move="folder_id" in body.model_fields_set,
            folder_id=body.folder_id, starred=body.starred, leo=body.leo,
        )  # fmt: skip
        return item_of(await manager.update(principal, file_id, changes))

    @router.delete("/{file_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_file(
        principal: Annotated[Principal, Depends(signed_in)], file_id: UUID
    ) -> Response:
        """Delete a file: gone for the person now, kept hidden 7 days for support."""
        await manager.delete(principal, file_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post("/{file_id}/copy", status_code=HTTPStatus.CREATED)
    async def copy_file(
        principal: Annotated[Principal, Depends(signed_in)],
        file_id: UUID,
        body: CopyBody | None = None,
    ) -> FileItem:
        """An instant copy sharing the stored bytes."""
        return item_of(await manager.copy(principal, file_id, named(body.name if body else None)))

    @router.post("/{file_id}/reindex")
    async def reindex_file(
        principal: Annotated[Principal, Depends(signed_in)], file_id: UUID
    ) -> FileItem:
        """Ask Leo to read a file it uses again."""
        return item_of(await manager.reindex(principal, file_id))

    @router.get("/{file_id}/download")
    async def download_file(
        principal: Annotated[Principal, Depends(signed_in)], file_id: UUID
    ) -> DownloadOut:
        """A 15-minute link to the bytes, through the edge."""
        link = await downloads.link(principal, file_id)
        return DownloadOut(url=link.url, expires_at=link.expires_at)

    @router.post("/{file_id}/transfer", status_code=HTTPStatus.NO_CONTENT)
    async def transfer_file(
        principal: Annotated[Principal, Depends(signed_in)], file_id: UUID, body: FileTransferBody
    ) -> Response:
        """Hand a file shared in a workspace over to it; it leaves My files and other workspaces."""
        await transfers.transfer(principal, file_id, body.workspace_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router


def build_folders_router(folders: Folders, ports: PortDirectory) -> APIRouter:
    """The person's folder routes."""
    router = APIRouter(prefix="/v1/files/folders", tags=["files"])
    signed_in = bearer_principal(ports)

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_folder(
        principal: Annotated[Principal, Depends(signed_in)], body: FolderBody
    ) -> FileFolder:
        """A new folder."""
        return folder_of(await folders.create(principal, valid_name(body.name)))

    @router.patch("/{folder_id}")
    async def update_folder(
        principal: Annotated[Principal, Depends(signed_in)], folder_id: UUID, body: FolderUpdate
    ) -> FileFolder:
        """Rename a folder or switch Leo's use of its files."""
        view = await folders.update(principal, folder_id, name=named(body.name), leo=body.leo)
        return folder_of(view)

    @router.delete("/{folder_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_folder(
        principal: Annotated[Principal, Depends(signed_in)], folder_id: UUID
    ) -> Response:
        """Remove a folder; its files move to the root."""
        await folders.delete(principal, folder_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
