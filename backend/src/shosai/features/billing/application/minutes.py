"""The month's meeting minutes: the live count, the allowance and the tombstones (BL-D3).

The month is the business calendar's month of the session's start (ADR 0058). Used seconds
are what every `MEETING_MINUTES` binding reports — the meetings that still exist, Leo's voice
conversations — plus the tombstones of deleted meetings; the count is never cached. A Free
account claims its desktop device on its first check there; a device another Free account
claimed refuses it. Paid accounts neither claim nor are refused.
"""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions, transaction_info
from shosai.core.kernel.business_calendar import BusinessCalendar
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import (
    MEETING_MINUTES,
    Entitlements,
    EntitlementSnapshot,
    FreeDeviceTakenError,
    MinutesExhaustedError,
    UploadExceedsMinutesError,
)
from shosai.features.billing.domain.meters import MinutesLeft, tombstones_since
from shosai.features.billing.infrastructure.minutes_records import (
    FreePlanDeviceRecord,
    UsageEventRecord,
)

# Длина id устройства или имени машины, которую клиент может прислать.
DEVICE_MAX: Final = 256

log = structlog.stdlib.get_logger(__name__)


def device_hash(device: str) -> bytes:
    """The SHA-256 of a device id or machine name, trimmed and case-folded."""
    return hashlib.sha256(device.strip().casefold().encode()).digest()


class MinutesMeter:
    """The `billing.minutes_allowance` and `billing.usage_tombstones` bindings."""

    def __init__(
        self,
        transactions: HomeTransactions,
        sources: tuple[Entitlements, PortDirectory],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        *,
        business: BusinessCalendar,
    ) -> None:
        self._transactions = transactions
        self._entitlements, self._ports = sources
        self._clock = clock
        self._business = business

    async def check(self, session: AsyncSession, user_id: UUID, device: str | None) -> MinutesLeft:
        """Minutes left this month; refused at the limit or on another Free account's device."""
        snapshot = await self._snapshot(session, user_id)
        if not snapshot.paid and device and device.strip():
            await claim_device(session, user_id, device[:DEVICE_MAX])
        left = await self._left(session, user_id, snapshot)
        if left.exhausted and left.limit_minutes is not None:
            raise MinutesExhaustedError(left.limit_minutes)
        return left

    async def covers(self, session: AsyncSession, user_id: UUID, seconds: int) -> MinutesLeft:
        """Minutes left when a recording of `seconds` fits them; refused before processing."""
        left = await self._left(session, user_id, await self._snapshot(session, user_id))
        if not left.covers(seconds):
            raise UploadExceedsMinutesError(left.remaining_minutes or 0)
        return left

    async def meeting_deleted(
        self, session: AsyncSession, user_id: UUID, meeting: tuple[UUID, datetime], seconds: int
    ) -> None:
        """Keep a deleted meeting's seconds in its month; nothing for a month no longer counted."""
        meeting_id, started_at = meeting
        if started_at < tombstones_since(self._clock(), self._business):
            return
        await session.execute(
            insert(UsageEventRecord)
            .values(
                id=new_id(),
                occurred_at=started_at,
                user_id=user_id,
                meeting_id=meeting_id,
                seconds=seconds,
            )
            .on_conflict_do_nothing(index_elements=["meeting_id", "occurred_at"])
        )

    async def used_seconds(self, home: Home, user_id: UUID, since: datetime) -> int:
        """Seconds used in the month starting at `since`, in a transaction of its own."""
        async with self._transactions.begin(TenancyScope(home, user_id), read_only=True) as session:
            return await self.used_in(session, user_id, self._business.month_window(since))

    async def used_in(
        self, session: AsyncSession, user_id: UUID, window: tuple[datetime, datetime]
    ) -> int:
        """Seconds of sessions started in the window: every binding's and the tombstones."""
        start, end = window
        tombstones = await session.scalar(
            select(func.coalesce(func.sum(UsageEventRecord.seconds), 0)).where(
                UsageEventRecord.user_id == user_id,
                UsageEventRecord.occurred_at >= start,
                UsageEventRecord.occurred_at < end,
            )
        )
        live = 0
        for meetings in self._ports.all(MEETING_MINUTES):
            live += await meetings.recorded_seconds(session, user_id, window)
        return int(tombstones or 0) + live

    async def _snapshot(self, session: AsyncSession, user_id: UUID) -> EntitlementSnapshot:
        home = transaction_info(session).scope.home
        return await self._entitlements.snapshot(home, user_id)

    async def _left(
        self, session: AsyncSession, user_id: UUID, snapshot: EntitlementSnapshot
    ) -> MinutesLeft:
        limit = snapshot.limits.meeting_minutes_per_month
        if limit is None:
            return MinutesLeft(None, 0)
        used = await self.used_in(session, user_id, self._business.month_window(self._clock()))
        return MinutesLeft(limit, used)


async def claim_device(session: AsyncSession, user_id: UUID, device: str) -> None:
    """Claim the device for this Free account, or refuse it when another one holds it."""
    digest = device_hash(device)
    claimed = await session.scalar(
        insert(FreePlanDeviceRecord)
        .values(device_hash=digest, user_id=user_id)
        .on_conflict_do_nothing(index_elements=["device_hash"])
        .returning(FreePlanDeviceRecord.user_id)
    )
    if claimed is not None:
        return
    # Чужую заявку RLS не покажет: видна только своя.
    own = await session.scalar(
        select(FreePlanDeviceRecord.user_id).where(FreePlanDeviceRecord.device_hash == digest)
    )
    if own != user_id:
        log.info("Устройство занято другим бесплатным аккаунтом")
        raise FreeDeviceTakenError
