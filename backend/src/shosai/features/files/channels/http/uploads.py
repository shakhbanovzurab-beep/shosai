"""The person's uploads straight to the bucket (`/v1/me/uploads*`; §10; FL-D1).

Create answers the part links, each signed for its exact length; the client PUTs the
parts to the bucket, then completes. Get answers the parts done and fresh links for the
rest, for a resumed upload. Errors use the platform's envelope: `upload_too_large`,
`storage_limit`, `storage_not_included`, `name_*`, `filename_invalid`, `upload_not_found`,
`upload_incomplete`, `upload_closed`.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.ports.directory import PortDirectory
from shosai.features.files.application.upload_links import UploadView
from shosai.features.files.application.upload_rules import UploadRequest
from shosai.features.files.application.uploads import UploadService
from shosai.features.files.domain.purposes import UploadPurpose
from shosai.features.files.domain.uploads import UploadState
from shosai.features.identity.contracts import Principal, bearer_principal


class UploadBody(BaseModel):
    """What the client is about to upload."""

    model_config = ConfigDict(extra="forbid")

    purpose: UploadPurpose
    filename: Annotated[str, Field(min_length=1, max_length=255)]
    content_type: Annotated[str, Field(max_length=255)]
    size_bytes: Annotated[int, Field(ge=1)]


class PartLinkView(BaseModel):
    """Where to PUT one part: the URL, the headers to send and the exact length."""

    number: int
    size_bytes: int
    url: str
    headers: dict[str, str]
    expires_at: datetime


class UploadAnswer(BaseModel):
    """An upload and, while it is pending, the links of the parts still to send."""

    id: UUID
    purpose: UploadPurpose
    state: UploadState
    filename: str
    content_type: str
    size_bytes: int
    expires_at: datetime
    done_parts: list[int]
    parts: list[PartLinkView]


def answer_of(view: UploadView) -> UploadAnswer:
    """The answer of an upload's view."""
    return UploadAnswer(
        id=view.id, purpose=view.purpose, state=view.state, filename=view.filename,
        content_type=view.content_type, size_bytes=view.size_bytes, expires_at=view.expires_at,
        done_parts=list(view.done_parts),
        parts=[
            PartLinkView(
                number=link.number, size_bytes=link.size_bytes, url=link.request.url,
                headers=dict(link.request.headers), expires_at=link.request.expires_at,
            )
            for link in view.links
        ],
    )  # fmt: skip


def build_uploads_router(uploads: UploadService, ports: PortDirectory) -> APIRouter:
    """The person's upload routes."""
    router = APIRouter(prefix="/v1/me/uploads", tags=["files"])
    signed_in = bearer_principal(ports)

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_upload(
        principal: Annotated[Principal, Depends(signed_in)], body: UploadBody
    ) -> UploadAnswer:
        """Start an upload: the part links, signed for 15 minutes each."""
        request = UploadRequest(body.purpose, body.filename, body.content_type, body.size_bytes)
        return answer_of(await uploads.create(principal, request))

    @router.get("/{upload_id}")
    async def read_upload(
        principal: Annotated[Principal, Depends(signed_in)], upload_id: UUID
    ) -> UploadAnswer:
        """The upload's state; while pending, the parts done and links for the rest."""
        return answer_of(await uploads.status(principal, upload_id))

    @router.post("/{upload_id}/complete")
    async def complete_upload(
        principal: Annotated[Principal, Depends(signed_in)], upload_id: UUID
    ) -> UploadAnswer:
        """Assemble the parts: ready, or rejected when the size is not the declared one."""
        return answer_of(await uploads.complete(principal, upload_id))

    @router.delete("/{upload_id}", status_code=HTTPStatus.NO_CONTENT)
    async def cancel_upload(
        principal: Annotated[Principal, Depends(signed_in)], upload_id: UUID
    ) -> Response:
        """Abandon an open upload and free what it reserved."""
        await uploads.cancel(principal, upload_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
