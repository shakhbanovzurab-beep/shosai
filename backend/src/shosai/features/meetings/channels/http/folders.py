"""A person's folders of meetings: `/v1/meetings/folders` (plan step 7b, MT-D7).

- `GET` pages the folders oldest first.
- `POST` makes one in the next colour (201), once per `Idempotency-Key` when one is sent.
- `PATCH /{id}` renames it.
- `DELETE /{id}` deletes it and leaves its meetings in no folder (204).

Errors: `folder_not_found`, `folder_name_required`, `folder_name_too_long`,
`idempotency_key_reused`, `invalid_cursor`.
"""

from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response

from shosai.core.idempotency.http import CLIENT_KEY_MAX_LENGTH, IDEMPOTENCY_KEY_HEADER
from shosai.core.pagination.page import Page, PageParameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.folders import Folders
from shosai.features.meetings.channels.http.library_models import FolderIn, FolderOut, folder_out

KEY_PATTERN: Final = r"^[A-Za-z0-9._:-]+$"
OptionalIdempotencyKey = Annotated[
    str | None,
    Header(
        alias=IDEMPOTENCY_KEY_HEADER,
        min_length=1,
        max_length=CLIENT_KEY_MAX_LENGTH,
        pattern=KEY_PATTERN,
        description="Optional: a key unique to one create, repeated on its retries.",
    ),
]


def build_folders_router(folders: Folders, ports: PortDirectory) -> APIRouter:
    """The person's folders."""
    router = APIRouter(prefix="/v1/meetings/folders", tags=["meetings"])
    signed_in = bearer_principal(ports)

    @router.get("")
    async def list_folders(
        principal: Annotated[Principal, Depends(signed_in)], page: PageParameters
    ) -> Page[FolderOut]:
        """Your folders, oldest first."""
        found = await folders.page(principal, page)
        return Page(items=[folder_out(f) for f in found.items], next_cursor=found.next_cursor)

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_folder(
        principal: Annotated[Principal, Depends(signed_in)],
        body: FolderIn,
        idempotency_key: OptionalIdempotencyKey = None,
    ) -> FolderOut:
        """Make a folder in the next colour."""
        return folder_out(await folders.create(principal, body.name, idempotency_key))

    @router.patch("/{folder_id}")
    async def rename_folder(
        principal: Annotated[Principal, Depends(signed_in)], folder_id: UUID, body: FolderIn
    ) -> FolderOut:
        """Rename a folder."""
        return folder_out(await folders.rename(principal, folder_id, body.name))

    @router.delete("/{folder_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_folder(
        principal: Annotated[Principal, Depends(signed_in)], folder_id: UUID
    ) -> Response:
        """Delete a folder; its meetings stay, in no folder."""
        await folders.delete(principal, folder_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
