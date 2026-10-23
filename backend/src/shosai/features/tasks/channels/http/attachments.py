"""A task's attachments (`/v1/tasks/{id}/attachments*`; tasks plan §3.13, ADR 0064).

A person who may read a task attaches their ready upload or a File Manager file, downloads
through files' 15-minute link and removes an attachment, which clears the cover it was.
Errors use the platform's envelope with the codes the cabinet words: `task_not_found`,
`attachment_not_found`, `file_not_found`, `upload_not_claimable`, `attachments_full`,
`jira_unsupported`, `storage_limit`, `storage_not_included`, `validation_error`.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.tasks.application.attachments import Attachments, FromFile, FromUpload
from shosai.features.tasks.channels.http.detail_models import AttachmentOut
from shosai.features.tasks.channels.http.out import Out
from shosai.features.tasks.channels.http.shapes import attachment_out
from shosai.features.tasks.channels.http.strict import Strict


class UploadSourceBody(Strict):
    """The person's ready `task_attachment` upload."""

    upload_id: UUID


class FileSourceBody(Strict):
    """A File Manager file the person may read, attached as a copy on its object."""

    file_id: UUID


class AttachmentDownloadOut(Out):
    """A short-lived link to an attachment's bytes."""

    url: str
    expires_at: datetime


def build_attachments_router(attachments: Attachments, ports: PortDirectory) -> APIRouter:
    """The routes of tasks' attachments."""
    router = APIRouter(prefix="/v1/tasks/{task_id}/attachments", tags=["tasks"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_attachment(
        principal: person, task_id: UUID, body: UploadSourceBody | FileSourceBody
    ) -> AttachmentOut:
        """Attach an upload or a File Manager file; at most 50 to a task."""
        source = (
            FromUpload(body.upload_id)
            if isinstance(body, UploadSourceBody)
            else FromFile(body.file_id)
        )
        return attachment_out(await attachments.create(principal, task_id, source))

    @router.get("/{attachment_id}/download")
    async def download_attachment(
        principal: person, task_id: UUID, attachment_id: UUID
    ) -> AttachmentDownloadOut:
        """A 15-minute link to the attachment's bytes."""
        link = await attachments.download(principal, task_id, attachment_id)
        return AttachmentDownloadOut(url=link.url, expires_at=link.expires_at)

    @router.delete("/{attachment_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_attachment(principal: person, task_id: UUID, attachment_id: UUID) -> Response:
        """Remove an attachment; it stops being the cover."""
        await attachments.delete(principal, task_id, attachment_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
