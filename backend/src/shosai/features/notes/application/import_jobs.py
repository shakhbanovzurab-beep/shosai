"""An import's job, read from its run (plan step 9b): `GET /v1/me/sessions/import/{job_id}`.

The job is the person's own import run: anyone else's, a run of another source or one
whose meeting is deleted (MT-D8) is 404 `import_job_not_found`. Its stage and progress
come from the run (`domain/native_import`), its name from the file the run was made from,
its meeting at once, and its failure code with the person's language for the words the
client shows.
"""

from dataclasses import dataclass
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, Principal
from shosai.features.notes.application.run_rows import progress_of
from shosai.features.notes.domain.native_import import JobStage, job_progress
from shosai.features.notes.domain.runs import RunSource, RunState
from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.run_records import RunRecord


@dataclass(frozen=True, slots=True)
class ImportJob:
    """An import's job as the native clients poll it."""

    id: UUID
    file_name: str
    stage: JobStage
    progress: float
    meeting_id: UUID
    error_code: str | None
    language: str | None


class ImportJobs:
    """The person's import jobs."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def job(self, principal: Principal, job_id: UUID) -> ImportJob:
        """The job of the person's import run; `import_job_not_found` otherwise."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            found = (
                await session.execute(
                    select(RunRecord, MeetingRecord.title)
                    .join(MeetingRecord, MeetingRecord.id == RunRecord.session_id)
                    .where(
                        RunRecord.id == job_id,
                        RunRecord.user_id == principal.user_id,
                        RunRecord.source == RunSource.IMPORT.value,
                        MeetingRecord.deleted_at.is_(None),
                    )
                )
            ).first()
            if found is None:
                raise AppError("import_job_not_found", HTTPStatus.NOT_FOUND)
            run, title = found
            stage, progress = job_progress(RunState(run.state), progress_of(run.stage_state))
            language = None
            if stage is JobStage.FAILED:
                profile = await self._ports.get(ACCOUNT_PROFILE_READER).profile(
                    session, principal.user_id
                )
                language = profile.language if profile is not None else None
        return ImportJob(
            id=run.id, file_name=run.source_filename or title, stage=stage, progress=progress,
            meeting_id=run.session_id, error_code=run.error_code, language=language,
        )  # fmt: skip
