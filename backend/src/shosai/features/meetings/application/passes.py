"""A room pass on meetings' routes: who holds it, and its renewal (meetings plan §3.3).

A pass is honoured only while its room is open and its principal is not removed; a pass of a
closed room or a removed principal is revoked on the spot, so the next use is refused at
once. Renewal gives a fresh pass for the same session and retires the old one.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus

from sqlalchemy import select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.domain.joining import ROOM_PASS_TTL, JoinRefusal
from shosai.features.meetings.domain.rooms import RoomState
from shosai.features.meetings.infrastructure.room_passes import PassHolder, RoomPasses
from shosai.features.meetings.infrastructure.room_records import RoomBanRecord, RoomRecord


class RoomPassInvalidError(AppError):
    """No pass, or one that is unknown or expired (401)."""

    def __init__(self) -> None:
        super().__init__("room_pass_invalid", HTTPStatus.UNAUTHORIZED)


@dataclass(frozen=True, slots=True)
class RenewedPass:
    """A fresh pass and when it expires."""

    token: str
    expires_at: datetime


class PassCheck:
    """Who a room pass lets in, checked against the room's state and bans."""

    def __init__(
        self,
        transactions: HomeTransactions,
        passes: RoomPasses,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._passes = passes
        self._clock = clock

    async def holder(self, token: str | None) -> PassHolder:
        """The pass's holder while its room is open and they are not removed."""
        holder = None if not token else await self._passes.holder(token)
        if holder is None:
            raise RoomPassInvalidError
        scope = TenancyScope(holder.home, holder.owner_id, holder.org_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            state = await session.scalar(
                select(RoomRecord.state).where(RoomRecord.id == holder.room_id)
            )
            banned = await session.scalar(
                select(RoomBanRecord.id).where(
                    RoomBanRecord.room_id == holder.room_id,
                    RoomBanRecord.principal == holder.principal,
                )
            )
        if state != RoomState.OPEN.value:
            await self._passes.revoke(holder.room_id, holder.principal)
            raise AppError(JoinRefusal.ROOM_FINISHED.value, HTTPStatus.GONE)
        if banned is not None:
            await self._passes.revoke(holder.room_id, holder.principal)
            raise AppError(JoinRefusal.REMOVED.value, HTTPStatus.FORBIDDEN)
        return holder

    async def renew(self, token: str | None) -> RenewedPass:
        """A fresh pass for the same session while the room is open."""
        if not token:
            raise RoomPassInvalidError
        holder = await self.holder(token)
        fresh = await self._passes.renew(token, holder)
        return RenewedPass(fresh, self._clock() + ROOM_PASS_TTL)
