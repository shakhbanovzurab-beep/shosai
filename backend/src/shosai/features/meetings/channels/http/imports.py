"""An uploaded recording becomes a meeting: `POST /v1/meetings/imports` (plan step 9a).

The body names the person's ready upload for a recording (files' `POST /v1/me/uploads`
with the purpose `recording`); the answer is 202 with the meeting and the run that
transcribes it, whose progress `GET /v1/me/runs/{id}` shows. A repeat answers the same.
Errors: `upload_not_claimable`, `meetings_not_kept`.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.imports import ImportStarted, RecordingImports


class ImportIn(BaseModel):
    """The upload to turn into a meeting."""

    model_config = ConfigDict(extra="forbid")

    upload_id: UUID


def build_imports_router(imports: RecordingImports, ports: PortDirectory) -> APIRouter:
    """The import of recordings."""
    router = APIRouter(prefix="/v1/meetings", tags=["meetings"])
    signed_in = bearer_principal(ports)

    @router.post("/imports", status_code=HTTPStatus.ACCEPTED)
    async def import_recording(
        principal: Annotated[Principal, Depends(signed_in)], body: ImportIn
    ) -> ImportStarted:
        """Turn your uploaded recording into a meeting with a transcript and notes."""
        return await imports.start(principal, body.upload_id)

    return router
