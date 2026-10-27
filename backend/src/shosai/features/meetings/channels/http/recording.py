"""A call's video recording: `/v1/meetings/rooms/{room_id}/recording` (MR-D4).

`POST` starts it and `DELETE` stops it, both 202: the recording's state then moves with the
SFU's reports and shows in the room's marks. Refusals in their order: `room_not_found` (404),
`room_closed` and `no_live_call` (409), `recording_not_in_plan` (403), `storage_limit` (413),
`recording_active` (409), `recordings_busy` (503); stopping without one is `recording_not_active`.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.recording import Recordings
from shosai.features.meetings.domain.recordings import RecordingState
from shosai.features.meetings.infrastructure.call_records import RoomRecordingRecord


class RecordingOut(BaseModel):
    """A call's video recording."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: UUID
    state: RecordingState
    started_at: datetime
    file_id: UUID | None = Field(description="The File Manager file, once written.")


def recording_out(record: RoomRecordingRecord) -> RecordingOut:
    """The contract's shape of a recording."""
    return RecordingOut(
        id=record.id,
        state=RecordingState(record.state),
        started_at=record.started_at,
        file_id=record.file_id,
    )


def build_recording_router(recordings: Recordings, ports: PortDirectory) -> APIRouter:
    """The owner's recording of a room's call."""
    router = APIRouter(prefix="/v1/meetings/rooms/{room_id}/recording", tags=["meetings"])
    signed_in = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.post("", status_code=HTTPStatus.ACCEPTED)
    async def start_meeting_recording(principal: signed_in, room_id: UUID) -> RecordingOut:
        """Start recording the call; everyone in it sees the mark."""
        return recording_out(await recordings.start(principal, room_id))

    @router.delete("", status_code=HTTPStatus.ACCEPTED)
    async def stop_meeting_recording(principal: signed_in, room_id: UUID) -> RecordingOut:
        """Stop recording the call; the file lands in File Manager."""
        return recording_out(await recordings.stop(principal, room_id))

    return router
