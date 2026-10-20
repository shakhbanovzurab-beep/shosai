"""The intake stage of a recording's run (§3.4 flow 5, MT-D10): read, measure, admit.

The recording is fetched to a scratch directory; `ffprobe` names its container and audio
codec from the header — anything outside the allowed list is refused
(`unsupported_audio_format`) before any decoder runs — and gives its length. A recording
over 6 hours is refused (`recording_too_long`), and so is one whose minutes do not fit
what the person has left (`upload_exceeds_minutes`, billing's `covers`, MT-D3); both end
the run before any paid call. An admitted recording gives its meeting its length.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.ports.directory import PortDirectory
from shosai.core.storage.port import ObjectStorage
from shosai.features.billing.contracts import MINUTES_ALLOWANCE, UploadExceedsMinutesError
from shosai.features.meetings.application.pipeline import StageFailedError, StageWork
from shosai.features.meetings.application.scratch import fetched, scratch
from shosai.features.meetings.application.stage_reads import present_meeting
from shosai.features.meetings.domain.minutes import seconds_between
from shosai.features.meetings.domain.recordings import MediaFacts, readable, too_long
from shosai.features.meetings.infrastructure.media_tools import (
    UNREADABLE,
    UNSUPPORTED,
    MediaError,
    MediaTools,
)
from shosai.features.meetings.infrastructure.meeting_records import MeetingRecord
from shosai.features.meetings.infrastructure.run_records import RunRecord

TOO_LONG: Final = "recording_too_long"
EXCEEDS_MINUTES: Final = "upload_exceeds_minutes"


class IntakeStage:
    """Reads, measures and admits a run's recording."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, Mapping[Home, ObjectStorage], MediaTools],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._storage, self._tools = collaborators
        self._clock = clock

    async def run(self, work: StageWork) -> None:
        """Admit the recording or end the run with the reason."""
        async with self._transactions.begin(work.scope, read_only=True) as session:
            await present_meeting(session, work.meeting_id)
            run = await session.get(RunRecord, work.run_id)
            key = run.audio_key if run is not None else None
        if key is None:
            raise StageFailedError(UNREADABLE)
        facts = await self._measured(work.scope.home, key)
        async with self._transactions.begin(work.scope) as session:
            meeting = await session.scalar(
                select(MeetingRecord).where(MeetingRecord.id == work.meeting_id).with_for_update()
            )
            run = await session.get(RunRecord, work.run_id)
            if meeting is None or run is None:
                raise StageFailedError(UNREADABLE)
            ended_at = meeting.started_at + timedelta(milliseconds=facts.duration_ms)
            seconds = seconds_between(meeting.started_at, ended_at)
            try:
                await self._ports.get(MINUTES_ALLOWANCE).covers(session, meeting.user_id, seconds)
            except UploadExceedsMinutesError:
                raise StageFailedError(EXCEEDS_MINUTES) from None
            meeting.ended_at, meeting.seconds = ended_at, seconds
            meeting.updated_at = self._clock()
            run.audio_duration_ms = facts.duration_ms

    async def _measured(self, home: Home, key: str) -> MediaFacts:
        try:
            async with scratch() as directory:
                facts = await self._tools.probe(await fetched(self._storage, home, key, directory))
        except MediaError as error:
            raise StageFailedError(error.code) from error
        if not readable(facts):
            raise StageFailedError(UNSUPPORTED)
        if facts.duration_ms <= 0:
            raise StageFailedError(UNREADABLE)
        if too_long(facts.duration_ms):
            raise StageFailedError(TOO_LONG)
        return facts
