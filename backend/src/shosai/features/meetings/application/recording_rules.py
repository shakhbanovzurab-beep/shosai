"""The rules of a call's recording that are not its flow (meetings A7, A15c): how a refusal
answers over HTTP, how LiveKit's egress statuses map to the recording's states, and the
recording's limits and file name.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Final

from shosai.core.config.sections import StorageSettings
from shosai.core.kernel.homes import Home
from shosai.features.meetings.domain.recordings import (
    RecordingFailure,
    RecordingRefusal,
    RecordingState,
)

REFUSAL_STATUS: Final = {
    RecordingRefusal.NOT_FOUND: HTTPStatus.NOT_FOUND,
    RecordingRefusal.ROOM_CLOSED: HTTPStatus.CONFLICT,
    RecordingRefusal.NO_LIVE_CALL: HTTPStatus.CONFLICT,
    RecordingRefusal.NOT_IN_PLAN: HTTPStatus.FORBIDDEN,
    RecordingRefusal.STORAGE_LIMIT: HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    RecordingRefusal.ALREADY_RECORDING: HTTPStatus.CONFLICT,
    RecordingRefusal.PLATFORM_BUSY: HTTPStatus.SERVICE_UNAVAILABLE,
}
# Статусы LiveKit: достигнутый предел LiveKit — целый файл, запись завершена.
STATES: Final = {
    "EGRESS_STARTING": RecordingState.STARTING,
    "EGRESS_ACTIVE": RecordingState.ACTIVE,
    "EGRESS_ENDING": RecordingState.ENDING,
    "EGRESS_COMPLETE": RecordingState.COMPLETE,
    "EGRESS_LIMIT_REACHED": RecordingState.COMPLETE,
    "EGRESS_FAILED": RecordingState.FAILED,
    "EGRESS_ABORTED": RecordingState.FAILED,
}
FAILURES: Final = {"EGRESS_ABORTED": RecordingFailure.EGRESS_ABORTED}
CONTENT_TYPE: Final = "video/mp4"
SETTLING: Final = timedelta(minutes=2)  # сколько ждать вебхука, прежде чем спросить SFU


@dataclass(frozen=True, slots=True)
class RecordingLimits:
    """The platform's bounds and the buckets as egress reaches them."""

    concurrent: int
    length: timedelta
    buckets: Mapping[Home, StorageSettings]
    endpoints: Mapping[Home, str | None]


def recording_file_name(title: str | None, started_at: datetime) -> str:
    """The File Manager name of a recording: the room's title, or "Meeting", and its start."""
    return f"{title or 'Meeting'} {started_at:%Y-%m-%d %H-%M}.mp4"
