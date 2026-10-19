"""Starting and ending meetings: the native start and end, and §10's end (plan §3.4 flows 1, 3).

A start checks the month's minutes and the Free plan's device in the person's transaction,
ends the person's other active meeting on the same device, and keeps the meeting unless the
person chose not to keep meetings. An end takes the meeting's row lock, so concurrent ends —
the shipped clients retry with a fresh `ended_at` — end it once: the first decides the
server's `ended_at`, writes `meetings.meeting.ended` and creates the one live run when the
meeting is kept and something was said; the others answer what is stored. A meeting not
kept is removed at its end, its minutes kept as billing's tombstone.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import MINUTES_ALLOWANCE, USAGE_TOMBSTONES
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.run_rows import ensure_run
from shosai.features.meetings.application.transcript_stats import spoken
from shosai.features.meetings.contracts import MeetingNotFoundError
from shosai.features.meetings.contracts.events import MeetingEnded
from shosai.features.meetings.domain.meetings import (
    EndCause,
    MeetingClock,
    MeetingSource,
    MeetingStatus,
    checked_title,
    end_meeting,
    needs_run,
    title_or_default,
)
from shosai.features.meetings.domain.minutes import seconds_between
from shosai.features.meetings.domain.runs import RunSource, idempotency_key
from shosai.features.meetings.infrastructure.meeting_records import (
    MEETING_RESOURCE,
    MeetingRecord,
)
from shosai.features.meetings.infrastructure.metrics import MeetingMetrics
from shosai.features.meetings.infrastructure.notes_records import SettingsRecord
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer

DEVICE_MAX: Final = 256
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MeetingSnapshot:
    """A meeting as the native start and end answer it."""

    meeting_id: UUID
    title: str
    status: MeetingStatus
    started_at: datetime
    ended_at: datetime | None
    client_device_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Ended:
    """A meeting after an end: its state and its live run, if it has one."""

    meeting: MeetingSnapshot
    run_id: UUID | None


def snapshot(record: MeetingRecord) -> MeetingSnapshot:
    """The meeting's answer."""
    return MeetingSnapshot(
        record.id, record.title, MeetingStatus(record.status), record.started_at,
        record.ended_at, record.client_device_id, record.created_at, record.updated_at,
    )  # fmt: skip


class MeetingLifecycle:
    """Starts, retitles and ends meetings for the person who manages them."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, EventOutbox, MeetingMetrics],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._outbox, self._metrics = collaborators
        self._clock = clock

    async def start(self, principal: Principal, title: str, device: str) -> MeetingSnapshot:
        """A new live meeting; 402 or 403 from billing when its minutes or device refuse it."""
        clean_device = device.strip()[:DEVICE_MAX] or None
        async with self._transactions.begin(principal.scope()) as session:
            await self._ports.get(MINUTES_ALLOWANCE).check(session, principal.user_id, clean_device)
            now = self._clock()
            if clean_device is not None:
                await self._replace_on_device(session, principal, clean_device)
            settings = await session.get(SettingsRecord, principal.user_id)
            record = MeetingRecord(
                id=new_id(),
                user_id=principal.user_id,
                title=title_or_default(title, now),
                status=MeetingStatus.ACTIVE.value,
                source=MeetingSource.LIVE.value,
                started_at=now,
                client_device_id=clean_device,
                kept=settings is None or settings.keep_meetings,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            await session.flush()
            started = snapshot(record)
        self._metrics.started(MeetingSource.LIVE)
        log.info("Встреча начата", meeting_id=str(started.meeting_id), kept=record.kept)
        return started

    async def update(
        self,
        principal: Principal,
        meeting_id: UUID,
        change: tuple[str | None, MeetingStatus | None, datetime | None],
    ) -> Ended:
        """Retitle the meeting and end it when the client says it is over; once."""
        title, status, asked = change
        async with self._transactions.begin(principal.scope()) as session:
            record = await self._managed(session, principal, meeting_id)
            if title is not None:
                record.title = checked_title(title)
                record.updated_at = self._clock()
            run_id = record.latest_run_id
            if status in {MeetingStatus.COMPLETED, MeetingStatus.FAILED}:
                cause = (
                    EndCause.CLIENT if status is MeetingStatus.COMPLETED else EndCause.CLIENT_FAILED
                )
                run_id = await self._close(session, record, cause, asked)
            return Ended(snapshot(record), run_id)

    async def end(self, principal: Principal, meeting_id: UUID) -> Ended:
        """§10's end: the same end as the client's, answering the live run."""
        return await self.update(principal, meeting_id, (None, MeetingStatus.COMPLETED, None))

    async def _managed(
        self, session: AsyncSession, principal: Principal, meeting_id: UUID
    ) -> MeetingRecord:
        """The meeting's row, locked; `MeetingNotFoundError` for any meeting not theirs."""
        record = await session.scalar(
            self._manageable(principal).where(MeetingRecord.id == meeting_id)
        )
        if record is None:
            raise MeetingNotFoundError
        return record

    async def close_swept(
        self, scope: TenancyScope, meeting_id: UUID, cause: EndCause, asked: datetime
    ) -> bool:
        """End a meeting the sweep found due, in its owner's scope; False if it already ended."""
        async with self._transactions.begin(scope) as session:
            record = await session.scalar(
                select(MeetingRecord)
                .where(
                    MeetingRecord.id == meeting_id,
                    MeetingRecord.status == MeetingStatus.ACTIVE.value,
                    MeetingRecord.deleted_at.is_(None),
                )
                .with_for_update()
            )
            if record is None:
                return False
            await self._close(session, record, cause, asked)
            return True

    def _manageable(self, principal: Principal) -> Select[MeetingRecord]:
        viewer = Viewer(principal.user_id)
        policy = self._ports.get(ACCESS_POLICY)
        return (
            select(MeetingRecord)
            .where(policy.manageable(MEETING_RESOURCE, viewer), MeetingRecord.deleted_at.is_(None))
            .with_for_update(of=MeetingRecord)
        )

    async def _replace_on_device(
        self, session: AsyncSession, principal: Principal, device: str
    ) -> None:
        """End the person's other active meetings on this device, at their last sign of life."""
        stale = await session.scalars(
            self._manageable(principal).where(
                MeetingRecord.client_device_id == device,
                MeetingRecord.status == MeetingStatus.ACTIVE.value,
            )
        )
        for record in stale.all():
            await self._close(session, record, EndCause.REPLACED, record.started_at)

    async def _close(
        self, session: AsyncSession, record: MeetingRecord, cause: EndCause, asked: datetime | None
    ) -> UUID | None:
        """End a locked meeting once; the live run's id, or None without one."""
        lines, last_line_end = await spoken(session, record)
        clock = MeetingClock(
            record.started_at, MeetingStatus(record.status), record.ended_at, last_line_end
        )
        ending = end_meeting(clock, cause=cause, now=self._clock(), asked=asked)
        if not ending.changed:
            return record.latest_run_id
        record.status, record.ended_at = ending.status.value, ending.ended_at
        record.seconds = seconds_between(record.started_at, ending.ended_at)
        record.line_count, record.updated_at = lines, self._clock()
        source = MeetingSource(record.source)
        await self._outbox.add(
            session,
            MeetingEnded(
                meeting_id=record.id, user_id=record.user_id, org_id=record.org_id,
                source=source, cause=cause, seconds=record.seconds,
            ),
        )  # fmt: skip
        self._metrics.ended(source, cause)
        log.info("Встреча закончилась", meeting_id=str(record.id), cause=cause.value, lines=lines)
        if not record.kept:
            await self._ports.get(USAGE_TOMBSTONES).meeting_deleted(
                session, record.user_id, (record.id, record.started_at), record.seconds
            )
            await session.delete(record)
            return None
        if not needs_run(kept=True, has_speech=lines > 0):
            return None
        run_id = await ensure_run(session, record, RunSource.LIVE, idempotency_key(RunSource.LIVE))
        record.latest_run_id = run_id
        return run_id
