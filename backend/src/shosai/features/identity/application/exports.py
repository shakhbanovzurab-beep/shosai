"""Asking for an export of everything Shosai keeps about the person, and downloading it.

A request queues a job unless one is already open, which it returns instead; a fourth
request within a day is refused. The latest job carries a 15-minute download link while its
archive lives, 7 days after it is ready.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.storage.port import Disposition, ObjectStorage
from shosai.features.identity.contracts import Principal
from shosai.features.identity.domain.export import (
    ARCHIVE_TYPE,
    REQUESTS_PER_DAY,
    ExportState,
)
from shosai.features.identity.infrastructure.export_records import OPEN, DataExportJob

DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class ExportView:
    """A job as the person sees it; the link exists only while the archive does."""

    id: UUID
    state: ExportState
    requested_at: datetime
    ready_at: datetime | None
    expires_at: datetime | None
    size_bytes: int | None
    download_url: str | None
    download_expires_at: datetime | None


class Exports:
    """The person's export jobs."""

    def __init__(
        self, transactions: HomeTransactions, objects: Mapping[Home, ObjectStorage]
    ) -> None:
        self._transactions = transactions
        self._objects = objects

    async def request(self, principal: Principal) -> ExportView:
        """Queue an archive, or return the one being made."""
        now = datetime.now(UTC)
        async with self._transactions.begin(principal.scope()) as session:
            job = await _open_job(session, principal.user_id)
            if job is None:
                await _check_daily_limit(session, principal.user_id, now)
                await session.execute(
                    insert(DataExportJob)
                    .values(
                        id=new_id(), user_id=principal.user_id,
                        state=ExportState.QUEUED.value, run_at=now,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[DataExportJob.user_id], index_where=text(OPEN)
                    )
                )  # fmt: skip
                # Параллельный запрос мог записать своё задание: тогда вернётся оно.
                job = await _open_job(session, principal.user_id)
        if job is None:
            message = "задание выгрузки не найдено сразу после записи"
            raise RuntimeError(message)
        return _view(job)

    async def latest(self, principal: Principal) -> ExportView | None:
        """The newest job, with a download link while its archive lives."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            job = await session.scalar(
                select(DataExportJob)
                .where(DataExportJob.user_id == principal.user_id)
                .order_by(DataExportJob.requested_at.desc(), DataExportJob.id.desc())
                .limit(1)
            )
        if job is None:
            return None
        view = _view(job)
        if job.object_key is None or job.expires_at is None or job.expires_at <= datetime.now(UTC):
            return view
        request = await self._objects[principal.home].presign_get(
            job.object_key,
            filename=f"shosai-export-{job.requested_at.date().isoformat()}.zip",
            disposition=Disposition.ATTACHMENT,
            content_type=ARCHIVE_TYPE,
        )
        return _view(job, request.url, request.expires_at)


OPEN_JOBS = DataExportJob.state.in_((ExportState.QUEUED.value, ExportState.RUNNING.value))


async def _open_job(session: AsyncSession, user_id: UUID) -> DataExportJob | None:
    return await session.scalar(
        select(DataExportJob).where(DataExportJob.user_id == user_id, OPEN_JOBS)
    )


async def _check_daily_limit(session: AsyncSession, user_id: UUID, now: datetime) -> None:
    recent = await session.scalar(
        select(func.count())
        .select_from(DataExportJob)
        .where(DataExportJob.user_id == user_id, DataExportJob.requested_at > now - DAY)
    )
    if (recent or 0) >= REQUESTS_PER_DAY:
        raise AppError("export_limit", HTTPStatus.TOO_MANY_REQUESTS)


def _view(
    job: DataExportJob, url: str | None = None, url_expires_at: datetime | None = None
) -> ExportView:
    return ExportView(
        id=job.id, state=ExportState(job.state), requested_at=job.requested_at,
        ready_at=job.ready_at, expires_at=job.expires_at, size_bytes=job.size_bytes,
        download_url=url, download_expires_at=url_expires_at,
    )  # fmt: skip
