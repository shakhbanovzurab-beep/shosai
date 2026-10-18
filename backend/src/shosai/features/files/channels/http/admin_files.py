"""Support's deleted files of a person (`/v1/admin/users/{user_id}/files*`, admin session; FL-D5).

The admin names the person and their home (both on the account's card): the list holds
the files deleted within the last 7 days, and a restore brings one back into the person's
File Manager and quota, shared nowhere.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict

from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.features.files.application.hidden_files import HiddenFiles
from shosai.features.identity.contracts import require_admin


class HiddenFileOut(BaseModel):
    """A deleted file support may still restore."""

    id: UUID
    name: str
    size_bytes: int
    deleted_at: datetime


class HiddenFilesOut(BaseModel):
    """A person's deleted files, the latest deletion first."""

    files: list[HiddenFileOut]


class RestoreBody(BaseModel):
    """The person's home, as the account's card shows it."""

    model_config = ConfigDict(extra="forbid")

    home: Home


def build_admin_files_router(hidden: HiddenFiles, ports: PortDirectory) -> APIRouter:
    """Support's routes over deleted files."""
    router = APIRouter(
        prefix="/v1/admin/users", tags=["admin"], dependencies=[Depends(require_admin(ports))]
    )

    @router.get("/{user_id}/files")
    async def list_hidden_files(user_id: UUID, home: Annotated[Home, Query()]) -> HiddenFilesOut:
        """The person's files deleted within the last 7 days."""
        found = await hidden.of_person(home, user_id)
        return HiddenFilesOut(
            files=[
                HiddenFileOut(
                    id=f.file_id, name=f.name, size_bytes=f.size_bytes, deleted_at=f.deleted_at
                )
                for f in found
            ]
        )

    @router.post("/{user_id}/files/{file_id}/restore", status_code=HTTPStatus.NO_CONTENT)
    async def restore_file(user_id: UUID, file_id: UUID, body: RestoreBody) -> Response:
        """Bring a deleted file back into the person's File Manager and quota."""
        await hidden.restore(body.home, user_id, file_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
