"""The export of the person's data: `POST /v1/me/exports`, `GET /v1/me/exports/latest`."""

from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shosai.core.kernel.errors import AppError
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.core.web.rate_limit import rate_limited
from shosai.features.identity.application.exports import Exports, ExportView
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.identity.domain.export import ExportState

EXPORT_LIMIT: Final = RateLimit("identity.export", 10, timedelta(minutes=1), 10)


class ExportJob(BaseModel):
    """An archive of everything Shosai keeps about the person, and where it is."""

    id: UUID
    state: ExportState
    requested_at: datetime
    ready_at: datetime | None
    expires_at: datetime | None
    size_bytes: int | None
    # Ссылка живёт 15 минут и выдаётся заново при каждом чтении.
    download_url: str | None
    download_expires_at: datetime | None


def job_of(view: ExportView) -> ExportJob:
    """The answer of a job."""
    return ExportJob(
        id=view.id, state=view.state, requested_at=view.requested_at, ready_at=view.ready_at,
        expires_at=view.expires_at, size_bytes=view.size_bytes, download_url=view.download_url,
        download_expires_at=view.download_expires_at,
    )  # fmt: skip


def build_export_router(exports: Exports, ports: PortDirectory, limiter: RateLimiter) -> APIRouter:
    """The export routes of the signed-in person."""
    router = APIRouter(
        prefix="/v1/me/exports",
        tags=["me"],
        dependencies=[Depends(rate_limited(limiter, EXPORT_LIMIT))],
    )
    signed_in = bearer_principal(ports)
    person = Annotated[Principal, Depends(signed_in)]

    @router.post("", status_code=HTTPStatus.ACCEPTED)
    async def request_export(principal: person) -> ExportJob:
        """Queue an archive, or return the one being made; 429 `export_limit` after 3 a day."""
        return job_of(await exports.request(principal))

    @router.get("/latest")
    async def latest_export(principal: person) -> ExportJob:
        """The newest archive; while it is kept, a download link valid for 15 minutes."""
        view = await exports.latest(principal)
        if view is None:
            raise AppError("export_not_found", HTTPStatus.NOT_FOUND)
        return job_of(view)

    return router
