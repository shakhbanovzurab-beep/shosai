"""Creating a meeting's run once per source and key (§8.1 Pipeline run, §10).

A run is created in the transaction of the effect that asks for it — the meeting's end, an
import, a recording, a rewrite of the notes — with every stage of its source pending. The
unique `(session_id, idempotency_key)` makes a repeat answer the run already there: the
client's end and the silence sweep both ask for the meeting's one `live` run.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.ids import new_id
from shosai.features.meetings.domain.runs import (
    RunSource,
    RunState,
    Stage,
    StageRecord,
    StageStatus,
    initial_progress,
)
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.run_records import RunRecord


def stage_state(progress: dict[Any, StageRecord]) -> dict[str, dict[str, object]]:
    """The JSON a run keeps of its stages."""
    return {
        stage.value: {
            "status": record.status.value,
            "attempts": record.attempts,
            "error_code": record.error_code,
        }
        for stage, record in progress.items()
    }


def progress_of(state: dict[str, Any]) -> dict[Stage, StageRecord]:
    """A run's stages as the JSON keeps them."""
    return {
        Stage(name): StageRecord(
            StageStatus(item.get("status", StageStatus.PENDING.value)),
            int(item.get("attempts", 0)),
            item.get("error_code"),
        )
        for name, item in state.items()
    }


async def ensure_run(
    session: AsyncSession, meeting: MeetingRecord, source: RunSource, key: str
) -> UUID:
    """The meeting's run of that key: created now with its stages pending, or the one there."""
    created: UUID | None = await session.scalar(
        insert(RunRecord)
        .values(
            id=new_id(),
            session_id=meeting.id,
            user_id=meeting.user_id,
            org_id=meeting.org_id,
            source=source.value,
            idempotency_key=key,
            state=RunState.PENDING.value,
            stage_state=stage_state(initial_progress(source)),
        )
        .on_conflict_do_nothing(index_elements=["session_id", "idempotency_key"])
        .returning(RunRecord.id)
    )
    if created is not None:
        return created
    existing: UUID | None = await session.scalar(
        select(RunRecord.id).where(
            RunRecord.session_id == meeting.id, RunRecord.idempotency_key == key
        )
    )
    if existing is None:
        message = "прогон встречи не создан и не найден"
        raise RuntimeError(message)
    return existing
