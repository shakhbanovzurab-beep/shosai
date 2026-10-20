"""The library's counts for its pills: `GET /v1/notes/counts` (the cabinet's library).

Registered before `/v1/notes/{meeting_id}`: the first match wins, and `counts` is no
meeting's id.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.notes.application.library_counts import MeetingCounts


class FolderCountOut(BaseModel):
    """How many of the person's meetings one of their folders holds."""

    folder_id: UUID
    count: int


class CountsOut(BaseModel):
    """Every meeting the person may read, and their own meetings per folder."""

    all: int = Field(description="Every meeting the person may read, shared ones included.")
    folders: list[FolderCountOut] = Field(
        description="The person's own meetings in each folder that holds any."
    )


def build_counts_router(counts: MeetingCounts, ports: PortDirectory) -> APIRouter:
    """The library's counts."""
    router = APIRouter(prefix="/v1/notes/counts", tags=["notes"])
    signed_in = bearer_principal(ports)

    @router.get("")
    async def library_counts(principal: Annotated[Principal, Depends(signed_in)]) -> CountsOut:
        """How many meetings the library holds, in all and per folder."""
        found = await counts.of(principal)
        return CountsOut(
            all=found.every,
            folders=[
                FolderCountOut(folder_id=folder_id, count=count)
                for folder_id, count in sorted(found.by_folder.items())
            ],
        )

    return router
