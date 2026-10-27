"""A call's video recording (MR-D4, meetings plan §3.5 flow 5).

The owner starts it on a paid plan with storage left, while a call goes on, when the room has
none running and the platform is under its concurrent limit — the checks in the domain's order.
The row is committed `starting` before the egress starts, so an early webhook finds it; the
egress writes the MP4 straight at the owner's File Manager key for the recording's id, and the
marks tell everyone it records. Reports move the row only forward; the first `complete` adopts
the file into File Manager and publishes `meetings.recording.ready`; a failure keeps its code.
The sweep stops a recording at its length limit and settles one whose webhook was lost.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.config.sections import StorageSettings
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.contracts.written_files import WRITTEN_FILES, WrittenFile
from shosai.features.identity.contracts import Principal as Person
from shosai.features.meetings.application.joining import FoundRoom
from shosai.features.meetings.application.room_reads import live_call, owned_room
from shosai.features.meetings.application.video_server import (
    BucketTarget,
    EgressReport,
    VideoServer,
    VideoUnavailableError,
)
from shosai.features.meetings.contracts.events import RecordingReady
from shosai.features.meetings.domain.recordings import (
    ACTIVE_STATES,
    RecordingFailure,
    RecordingRefusal,
    RecordingState,
    StartFacts,
    advanced,
    start_refusal,
)
from shosai.features.meetings.domain.wire import RoomMarks, room_metadata
from shosai.features.meetings.infrastructure.call_records import RoomRecordingRecord
from shosai.features.meetings.infrastructure.room_records import RoomRecord

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
log = structlog.stdlib.get_logger(__name__)


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


class Recordings:
    """Video recordings of the owner's calls."""

    def __init__(
        self,
        transactions: HomeTransactions,
        services: tuple[VideoServer, PortDirectory, EventOutbox],
        limits: RecordingLimits,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._server, self._ports, self._outbox = services
        self._limits = limits
        self._clock = clock

    async def start(self, person: Person, room_id: UUID) -> RoomRecordingRecord:
        """Start the room's recording, or refuse with the first check it fails."""
        snapshot = await self._ports.get(ENTITLEMENTS).snapshot(person.home, person.user_id)
        left = await self._ports.get(WRITTEN_FILES).bytes_left(person.home, person.user_id)
        running = len(await self._server.egresses())
        async with self._transactions.begin(person.scope(), read_only=True) as session:
            room = await owned_room(session, person.user_id, room_id)
        scope = TenancyScope(person.home, person.user_id, room.org_id)
        async with self._transactions.begin(scope) as session:
            room = await owned_room(session, person.user_id, room_id, lock=True)
            active = await self._active(session, room_id)
            refusal = start_refusal(
                StartFacts(
                    is_owner=True, room_open=room.state == "open",
                    call_live=await live_call(session, room_id) is not None,
                    in_plan=snapshot.paid, storage_left_bytes=1 if left is None else left,
                    room_recording=active is not None, platform_active=running,
                    platform_concurrent=self._limits.concurrent,
                )
            )  # fmt: skip
            if refusal is not None:
                raise AppError(refusal.value, REFUSAL_STATUS[refusal])
            record = RoomRecordingRecord(
                id=new_id(), room_id=room_id, owner_id=person.user_id, org_id=room.org_id,
                state=RecordingState.STARTING.value, started_at=self._clock(),
            )  # fmt: skip
            record.s3_key = self._ports.get(WRITTEN_FILES).key_for(person.user_id, record.id)
            session.add(record)
            lk_room_name, notes_on = room.lk_room_name, room.notes_on
        target = self._target(person.home, record.s3_key)
        try:
            egress_id = await self._server.record(lk_room_name, target)
        except AppError:
            await self._settle(
                scope, record.id, RecordingState.FAILED, RecordingFailure.START_REFUSED
            )
            raise
        async with self._transactions.begin(scope) as session:
            await session.execute(
                update(RoomRecordingRecord)
                .where(RoomRecordingRecord.id == record.id)
                .values(egress_id=egress_id)
            )
        await self._server.set_metadata(
            lk_room_name, room_metadata(room_id, RoomMarks(notes=notes_on, recording=True))
        )
        log.info("Запись звонка начата", room_id=str(room_id), recording_id=str(record.id))
        return record

    async def stop(self, person: Person, room_id: UUID) -> RoomRecordingRecord:
        """Stop the room's recording; one already ending is answered as it is."""
        async with self._transactions.begin(person.scope(), read_only=True) as session:
            room = await owned_room(session, person.user_id, room_id)
            active = await self._active(session, room_id)
        if active is None:
            raise AppError("recording_not_active", HTTPStatus.CONFLICT)
        if active.egress_id is not None:
            await self._server.stop_egress(active.egress_id)
        scope = TenancyScope(person.home, person.user_id, room.org_id)
        return await self._settle(scope, active.id, RecordingState.ENDING, None)

    async def on_report(self, found: FoundRoom, report: EgressReport) -> None:
        """Move the recording of the egress forward; its first `complete` becomes a file."""
        state = STATES.get(report.status)
        if state is None:
            return
        scope = TenancyScope(found.home, found.owner_id, found.org_id)
        async with self._transactions.begin(scope) as session:
            record = await session.scalar(
                select(RoomRecordingRecord)
                .where(RoomRecordingRecord.egress_id == report.egress_id)
                .with_for_update()
            )
            if record is None:
                return
            before = RecordingState(record.state)
            after = advanced(before, state)
            if after is before:
                return
            # Время конца — раньше состояния: проверка базы связывает конец с завершённой записью.
            if after not in ACTIVE_STATES:
                record.ended_at = self._clock()
            if after is RecordingState.FAILED:
                record.error_code = FAILURES.get(
                    report.status, RecordingFailure.EGRESS_FAILED
                ).value
            record.state = after.value
            if after is RecordingState.COMPLETE:
                await self._complete(session, found, record, report)
            room = await session.get_one(RoomRecord, record.room_id)
            lk_room_name, notes_on = room.lk_room_name, room.notes_on
        if after not in ACTIVE_STATES:
            await self._server.set_metadata(
                lk_room_name,
                room_metadata(found.room_id, RoomMarks(notes=notes_on, recording=False)),
            )

    async def reconcile(self, home: Home, now: datetime) -> None:
        """Stop recordings at their length limit and settle those whose webhook was lost."""
        try:
            running = {report.egress_id for report in await self._server.egresses()}
        except VideoUnavailableError:
            return
        scope = TenancyScope(home)
        async with self._transactions.begin(scope, read_only=True, sweep=True) as session:
            rows = (
                await session.execute(
                    select(RoomRecordingRecord, RoomRecord.lk_room_name)
                    .join(RoomRecord, RoomRecord.id == RoomRecordingRecord.room_id)
                    .where(RoomRecordingRecord.state.in_([state.value for state in ACTIVE_STATES]))
                )
            ).all()
        for record, _lk_room_name in rows:
            found = FoundRoom(home, record.room_id, record.owner_id, record.org_id)
            owner = TenancyScope(home, record.owner_id, record.org_id)
            settled = now - record.started_at > SETTLING
            if record.egress_id is None:
                if settled:
                    await self._settle(
                        owner, record.id, RecordingState.FAILED, RecordingFailure.START_REFUSED
                    )
            elif record.egress_id not in running and settled:
                report = await self._server.egress(record.egress_id)
                if report is None:
                    await self._settle(
                        owner, record.id, RecordingState.FAILED, RecordingFailure.EGRESS_LOST
                    )
                else:
                    await self.on_report(found, report)
            elif now - record.started_at >= self._limits.length:
                await self._server.stop_egress(record.egress_id)
                log.info("Запись остановлена на пределе длины", recording_id=str(record.id))

    async def _complete(
        self,
        session: AsyncSession,
        found: FoundRoom,
        record: RoomRecordingRecord,
        report: EgressReport,
    ) -> None:
        room = await session.get_one(RoomRecord, record.room_id)
        record.size_bytes = report.size_bytes
        record.duration_seconds = report.duration_seconds
        written = WrittenFile(
            file_id=record.id, user_id=record.owner_id,
            name=recording_file_name(room.title, record.started_at),
            content_type=CONTENT_TYPE, size_bytes=report.size_bytes,
        )  # fmt: skip
        record.file_id = await self._ports.get(WRITTEN_FILES).adopt(session, written)
        await self._outbox.add(
            session,
            RecordingReady(
                recording_id=record.id, room_id=record.room_id, file_id=record.file_id,
                owner_id=found.owner_id, org_id=found.org_id, seconds=report.duration_seconds,
            ),
        )  # fmt: skip

    async def _active(self, session: AsyncSession, room_id: UUID) -> RoomRecordingRecord | None:
        return await session.scalar(
            select(RoomRecordingRecord).where(
                RoomRecordingRecord.room_id == room_id,
                RoomRecordingRecord.state.in_([state.value for state in ACTIVE_STATES]),
            )
        )

    async def _settle(
        self,
        scope: TenancyScope,
        recording_id: UUID,
        state: RecordingState,
        failure: RecordingFailure | None,
    ) -> RoomRecordingRecord:
        async with self._transactions.begin(scope) as session:
            record = await session.get_one(RoomRecordingRecord, recording_id, with_for_update=True)
            after = advanced(RecordingState(record.state), state)
            if after is RecordingState.FAILED and record.error_code is None:
                record.error_code = (failure or RecordingFailure.EGRESS_FAILED).value
                record.ended_at = self._clock()
            record.state = after.value
            return record

    def _target(self, home: Home, key: str | None) -> BucketTarget:
        bucket = self._limits.buckets[home]
        return BucketTarget(
            endpoint=self._limits.endpoints.get(home) or str(bucket.s3_endpoint_url).rstrip("/"),
            region=bucket.s3_region, bucket=bucket.s3_bucket,
            access_key=bucket.s3_access_key_id,
            secret=bucket.s3_secret_access_key.get_secret_value(),
            key=key or "",
        )  # fmt: skip
