"""Leo's voice conversations against the plan's monthly minutes (ADR 0070 LV-D7, BL-D3).

Billing reads the seconds of the person's conversations through `MEETING_MINUTES`, beside
their meetings. A conversation writes its row when it opens and its seconds every minute
(`VoiceMeter`), so the count is at most a minute behind; every minute the conversation asks
billing again whether minutes remain, and ends when none do. The meter also keeps the
person's lock of one conversation alive.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.kv.locks import LockLease, LockUnavailableError
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import MINUTES_ALLOWANCE, MinutesExhaustedError
from shosai.features.capture.domain.voice import VoiceEnd
from shosai.features.capture.infrastructure.voice_records import SECONDS_MAX, VoiceSessionRecord
from shosai.features.identity.contracts import Principal

SESSION = VoiceSessionRecord
# Блокировка «один разговор на человека» живёт дольше минуты, между продлениями.
LOCK_TTL: Final = timedelta(seconds=90)
log = structlog.stdlib.get_logger(__name__)


class VoiceMinutesCount:
    """The `billing.meeting_minutes` binding of capture: seconds of voice conversations."""

    async def recorded_seconds(
        self, session: AsyncSession, user_id: UUID, window: tuple[datetime, datetime]
    ) -> int:
        """Seconds of the person's conversations started in `[start, end)`."""
        start, end = window
        total = await session.scalar(
            select(func.coalesce(func.sum(SESSION.seconds), 0)).where(
                SESSION.user_id == user_id, SESSION.started_at >= start, SESSION.started_at < end
            )
        )
        return int(total or 0)


async def minutes_left(
    transactions: HomeTransactions, ports: PortDirectory, person: Principal
) -> None:
    """Refuse a conversation when the month's minutes are used up (402 `minutes_exhausted`)."""
    async with transactions.begin(person.scope()) as session:
        await ports.get(MINUTES_ALLOWANCE).check(session, person.user_id, None)


class VoiceMeter:
    """One conversation's row of minutes and its person's lock, kept minute by minute."""

    def __init__(
        self,
        parts: tuple[HomeTransactions, PortDirectory, LockLease],
        person: Principal,
        clock: Callable[[], datetime],
    ) -> None:
        self._transactions, self._ports, self._lease = parts
        self._person = person
        self._clock = clock
        self.id = new_id()
        self.started_at = clock()

    async def open(self) -> None:
        """Write the conversation's row."""
        async with self._transactions.begin(self._person.scope()) as session:
            session.add(
                SESSION(
                    id=self.id, started_at=self.started_at, user_id=self._person.user_id, seconds=0
                )
            )

    async def minute(self) -> bool:
        """Count the seconds so far, keep the lock; False when the month's minutes are used up."""
        await self._keep_lock()
        try:
            async with self._transactions.begin(self._person.scope()) as session:
                await self._count(session)
                await self._ports.get(MINUTES_ALLOWANCE).check(session, self._person.user_id, None)
        except MinutesExhaustedError:
            return False
        except AppError as unread:
            # Тариф не прочитан (503): разговор идёт, секунды уже записаны следующей минутой.
            log.warning("Минуты голосового разговора не проверены", code=unread.code)
        return True

    async def finish(self, end: VoiceEnd) -> None:
        """Count the last seconds and the end."""
        async with self._transactions.begin(self._person.scope()) as session:
            await self._count(session, end)

    def seconds(self) -> int:
        """Whole seconds since the conversation opened."""
        elapsed = int((self._clock() - self.started_at).total_seconds())
        return min(max(elapsed, 0), SECONDS_MAX)

    async def _count(self, session: AsyncSession, end: VoiceEnd | None = None) -> None:
        ending = {"ended_at": self._clock(), "end_code": end.value} if end is not None else {}
        await session.execute(
            update(SESSION)
            .where(SESSION.id == self.id, SESSION.started_at == self.started_at)
            .values(seconds=self.seconds(), **ending)
        )

    async def _keep_lock(self) -> None:
        try:
            kept = await self._lease.extend(LOCK_TTL)
        except LockUnavailableError:
            log.warning("Valkey не продлил блокировку голосового разговора")
            return
        if not kept:
            log.warning("Блокировка голосового разговора истекла до продления")
