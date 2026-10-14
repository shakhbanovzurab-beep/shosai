"""Making export archives: claimed by a sweep, written by a task, purged after 7 days.

The sweep claims queued jobs and counts each attempt; a job claimed again after 3 attempts
is given up. The task streams every owner's files into one ZIP in the home's bucket — no
transaction is open while storage is called — then marks the job ready and mails the
person in the same transaction. An archive whose job vanished meanwhile, because the
account was erased, is deleted at once.
"""

import json
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, select, update

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS, AccountRef
from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.messages import EmailKind, OutgoingEmail
from shosai.core.email.port import EmailPort
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.core.schedule.due_rows import DueRows, claim_due
from shosai.core.storage.port import MultipartUploads, ObjectStorage
from shosai.features.identity.domain.accounts import AccountState
from shosai.features.identity.domain.export import (
    EXPORT_KEPT,
    MANIFEST,
    MAX_ATTEMPTS,
    OPEN_STATES,
    ExportState,
    archive_key,
    archive_path,
)
from shosai.features.identity.emails.export_ready import EXPORT_READY_KEY
from shosai.features.identity.infrastructure.export_archive import ArchiveEntry, write_archive
from shosai.features.identity.infrastructure.export_records import DataExportJob
from shosai.features.identity.infrastructure.records import User

SWEEP_LIMIT: Final = 20
# Дольше дедлайна задачи: пока она жива, обход её не дублирует.
SWEEP_LEASE: Final = timedelta(minutes=45)
PURGE_BATCH: Final = 100
FAILED_KEPT: Final = timedelta(days=7)
JOBS: Final = DataExportJob.metadata.tables["data_export_jobs"]
DUE: Final = DueRows(
    table=JOBS,
    key=JOBS.c.id,
    run_at=JOBS.c.run_at,
    pending=JOBS.c.state.in_([state.value for state in OPEN_STATES]),
)
log = structlog.stdlib.get_logger(__name__)


class ExportRunner:
    """Claims, writes and purges the archives of one process."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        storage: tuple[Mapping[Home, ObjectStorage], Mapping[Home, MultipartUploads]],
        email: EmailPort,
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._objects, self._uploads = storage
        self._email = email

    async def start_due(self, home: Home) -> list[UUID]:
        """Claim the home's due jobs; the ones to run now, the rest given up."""
        ready: list[UUID] = []
        async with self._transactions.begin(TenancyScope(home)) as session:
            for row in await claim_due(session, DUE, limit=SWEEP_LIMIT, lease=SWEEP_LEASE):
                given_up = row.attempts >= MAX_ATTEMPTS
                values = (
                    {"state": ExportState.FAILED.value, "error_code": "export_failed"}
                    if given_up
                    else {"attempts": row.attempts + 1}
                )
                await session.execute(
                    update(DataExportJob).where(DataExportJob.id == row.id).values(values)
                )
                if given_up:
                    log.warning("Выгрузка не собрана за отведённые попытки", job_id=str(row.id))
                else:
                    ready.append(row.id)
        return ready

    async def make(self, home: Home, job_id: UUID) -> None:
        """Write the job's archive and mark it ready; nothing for a job no longer open."""
        user_id = await self._start(home, job_id)
        if user_id is None:
            return
        account = AccountRef(user_id, home)
        key = archive_key(user_id, job_id)
        size = await write_archive(self._uploads[home], key, self._entries(account))
        if not await self._finish(account, job_id, key, size):
            await self._objects[home].delete(key)

    async def purge(self, home: Home) -> int:
        """Delete the archives kept 7 days and the jobs of failures older than that."""
        now = datetime.now(UTC)
        async with self._transactions.begin(TenancyScope(home), read_only=True) as session:
            expired = (
                await session.execute(
                    select(DataExportJob.id, DataExportJob.object_key)
                    .where(
                        DataExportJob.state == ExportState.READY.value,
                        DataExportJob.expires_at < now,
                    )
                    .limit(PURGE_BATCH)
                )
            ).all()
        keys = [key for _, key in expired if key is not None]
        if keys:
            await self._objects[home].delete_many(keys)
        async with self._transactions.begin(TenancyScope(home)) as session:
            await session.execute(
                delete(DataExportJob).where(DataExportJob.id.in_([job for job, _ in expired]))
            )
            await session.execute(
                delete(DataExportJob).where(
                    DataExportJob.state == ExportState.FAILED.value,
                    DataExportJob.requested_at < now - FAILED_KEPT,
                )
            )
        return len(expired)

    async def _start(self, home: Home, job_id: UUID) -> UUID | None:
        async with self._transactions.begin(TenancyScope(home)) as session:
            job = await session.get(DataExportJob, job_id, with_for_update=True)
            if job is None or ExportState(job.state) not in OPEN_STATES:
                return None
            user = await session.get(User, job.user_id)
            if user is None or user.state != AccountState.ACTIVE:
                job.state, job.error_code = ExportState.FAILED.value, "account_unavailable"
                return None
            job.state, job.started_at = ExportState.RUNNING.value, datetime.now(UTC)
            return job.user_id

    async def _entries(self, account: AccountRef) -> AsyncIterator[ArchiveEntry]:
        """Every owner's files in its folder, then the manifest that lists them."""
        paths: list[str] = []
        for handler in sorted(self._ports.all(ACCOUNT_DATA_HANDLERS), key=lambda h: h.owner):
            async for file in handler.export(account):
                path = archive_path(handler.owner, file.name)
                paths.append(path)
                yield path, file.chunks
        manifest = {
            "account": str(account.user_id), "home": account.home.value,
            "created_at": datetime.now(UTC).isoformat(), "files": paths,
        }  # fmt: skip
        yield MANIFEST, _once(json.dumps(manifest, indent=2).encode())

    async def _finish(self, account: AccountRef, job_id: UUID, key: str, size: int) -> bool:
        now = datetime.now(UTC)
        async with self._transactions.begin(TenancyScope(account.home, account.user_id)) as session:
            job = await session.get(DataExportJob, job_id, with_for_update=True)
            user = await session.get(User, account.user_id)
            if job is None or job.state != ExportState.RUNNING or user is None:
                return False
            job.state, job.ready_at = ExportState.READY.value, now
            job.expires_at, job.object_key, job.size_bytes = now + EXPORT_KEPT, key, size
            await self._email.enqueue(
                session,
                OutgoingEmail(
                    recipient=user.email, kind=EmailKind.ACCOUNT, template=EXPORT_READY_KEY,
                    locale=user.language, user_id=user.id,
                    params={"days": EXPORT_KEPT.days},
                ),
            )  # fmt: skip
        return True


async def _once(data: bytes) -> AsyncIterator[bytes]:
    yield data
