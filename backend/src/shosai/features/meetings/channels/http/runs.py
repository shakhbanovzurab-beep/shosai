"""§10's end of a meeting and its run: `POST /v1/me/sessions/{id}/end`, `GET /v1/me/runs/{id}`.

The end answers 202 with the meeting's live run, or `run_id: null` when nothing was said
or the meeting is not kept; a repeat answers the same run. A run is read by whoever may
read its meeting, its stages and its state: pending, running, succeeded, partially
completed or failed. Errors: `meeting_not_found`, `run_not_found`.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.lifecycle import MeetingLifecycle
from shosai.features.meetings.application.runs_view import RunViews
from shosai.features.meetings.domain.runs import RunSource, RunState, Stage, StageStatus


class EndAccepted(BaseModel):
    """The meeting ended; its notes come from this run, if it has one."""

    run_id: UUID | None


class RunStageOut(BaseModel):
    """One stage of a run."""

    stage: Stage
    status: StageStatus
    attempts: int
    error_code: str | None


class RunOut(BaseModel):
    """A run of a meeting and how far it got."""

    id: UUID
    meeting_id: UUID
    source: RunSource
    state: RunState
    stages: list[RunStageOut]
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None


def build_runs_router(
    services: tuple[MeetingLifecycle, RunViews], ports: PortDirectory
) -> APIRouter:
    """§10's end and the run it starts."""
    lifecycle, runs = services
    router = APIRouter(prefix="/v1/me", tags=["meetings"])
    signed_in = bearer_principal(ports)

    @router.post("/sessions/{session_id}/end", status_code=HTTPStatus.ACCEPTED)
    async def end_session(
        principal: Annotated[Principal, Depends(signed_in)], session_id: UUID
    ) -> EndAccepted:
        """End the meeting; its notes follow from the run."""
        ended = await lifecycle.end(principal, session_id)
        return EndAccepted(run_id=ended.run_id)

    @router.get("/runs/{run_id}")
    async def get_run(principal: Annotated[Principal, Depends(signed_in)], run_id: UUID) -> RunOut:
        """A run of a meeting the person may read."""
        view = await runs.get(principal, run_id)
        return RunOut(
            id=view.run_id,
            meeting_id=view.meeting_id,
            source=view.source,
            state=view.state,
            stages=[
                RunStageOut(
                    stage=s.stage, status=s.status, attempts=s.attempts, error_code=s.error_code
                )
                for s in view.stages
            ],
            error_code=view.error_code,
            created_at=view.created_at,
            finished_at=view.finished_at,
        )

    return router
