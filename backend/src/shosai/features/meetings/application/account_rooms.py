"""A person's rooms when their account goes away or is frozen (meetings plan §3.5 flow 7).

When identity schedules a deletion or the admin blocks an account, every open room of the
person — in Personal and in every workspace — closes for good with `account` as its closer:
its link answers as an unknown one, and its call ends. The rooms are found by the sweep role
and each is closed in its own space's transaction; the SFU rooms end after the commits, and
one the SFU could not end is ended by the sweep. A repeat closes nothing more.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select, update

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.application.video_server import VideoServer, VideoUnavailableError
from shosai.features.meetings.domain.rooms import ClosedBy, RoomState
from shosai.features.meetings.infrastructure.room_records import RoomRecord

log = structlog.stdlib.get_logger(__name__)


class AccountRooms:
    """Closing a person's open rooms in their home."""

    def __init__(
        self,
        transactions: HomeTransactions,
        server: VideoServer,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._server = server
        self._clock = clock

    async def close_all(self, home: Home, user_id: UUID) -> int:
        """Close the person's open rooms; how many this run closed."""
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            rooms = (
                await session.execute(
                    select(RoomRecord.id, RoomRecord.org_id, RoomRecord.lk_room_name).where(
                        RoomRecord.owner_id == user_id, RoomRecord.state == RoomState.OPEN.value
                    )
                )
            ).all()
        closed: list[str] = []
        for room_id, org_id, lk_room_name in rooms:
            scope = TenancyScope(home, user_id, org_id)
            async with self._transactions.begin(scope) as session:
                now = self._clock()
                done = await session.execute(
                    update(RoomRecord)
                    .where(RoomRecord.id == room_id, RoomRecord.state == RoomState.OPEN.value)
                    .values(
                        state=RoomState.CLOSED.value,
                        closed_at=now,
                        closed_by=ClosedBy.ACCOUNT.value,
                        updated_at=now,
                    )
                )
            if done.rowcount:  # type: ignore[attr-defined]
                closed.append(lk_room_name)
        for lk_room_name in closed:
            try:
                await self._server.delete_room(lk_room_name)
            except VideoUnavailableError:
                log.warning("SFU не закончил комнату аккаунта; её закончит обход")
        log.info("Комнаты аккаунта закрыты", user_id=str(user_id), rooms=len(closed))
        return len(closed)
