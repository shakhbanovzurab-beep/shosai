"""A run as its client polls it (`GET /v1/me/runs/{run_id}`, §10).

A run is read by whoever may read its meeting, through the access policy; a run of a
meeting the person cannot read, or of a deleted one, is not found.
"""

from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.visibility import visible_meetings
from shosai.features.meetings.domain.runs import RunSource, RunState, Stage, StageStatus
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.run_records import RunRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer


class RunNotFoundError(AppError):
    """No such run the person may read (404)."""

    def __init__(self) -> None:
        super().__init__("run_not_found", HTTPStatus.NOT_FOUND)


@dataclass(frozen=True, slots=True)
class StageView:
    """One stage of a run."""

    stage: Stage
    status: StageStatus
    attempts: int
    error_code: str | None


@dataclass(frozen=True, slots=True)
class RunView:
    """A run, its stages and its outcome."""

    run_id: UUID
    meeting_id: UUID
    source: RunSource
    state: RunState
    stages: tuple[StageView, ...]
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None


class RunViews:
    """Reads runs for the person."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def get(self, principal: Principal, run_id: UUID) -> RunView:
        """The run, or `RunNotFoundError`."""
        meetings = visible_meetings(self._ports.get(ACCESS_POLICY), Viewer(principal.user_id))
        readable = meetings.with_only_columns(MeetingRecord.id).subquery()
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            run = await session.scalar(
                select(RunRecord).where(
                    RunRecord.id == run_id, RunRecord.session_id.in_(select(readable.c.id))
                )
            )
            if run is None:
                raise RunNotFoundError
            return view_of(run)


def view_of(run: RunRecord) -> RunView:
    """The run as its client reads it."""
    stages = tuple(
        StageView(
            Stage(name),
            StageStatus(state.get("status", StageStatus.PENDING.value)),
            int(state.get("attempts", 0)),
            state.get("error_code"),
        )
        for name, state in run.stage_state.items()
    )
    return RunView(
        run.id, run.session_id, RunSource(run.source), RunState(run.state), stages,
        run.error_code, run.created_at, run.finished_at,
    )  # fmt: skip
