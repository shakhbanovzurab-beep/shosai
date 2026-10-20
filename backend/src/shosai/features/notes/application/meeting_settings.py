"""A person's meetings setting, "Don't keep my meetings" (MT-D6), and its native mirror.

With the setting on, a meeting is shown live and then forgotten: no transcript, notes,
recording or share is stored, and only its minutes stay counted. A meeting takes the
setting when it starts. Before a person sets it, meetings are kept. The native
`/v1/auth/me` carries it as the draft's `no_logs`, which the desktop clients gate their
recording on.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert

from shosai.core.db.transactions import HomeTransactions
from shosai.features.identity.contracts import Principal
from shosai.features.notes.infrastructure.notes_records import SettingsRecord


class MeetingSettings:
    """Reads and writes the person's meetings setting."""

    def __init__(
        self,
        transactions: HomeTransactions,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._clock = clock

    async def keeps_meetings(self, principal: Principal) -> bool:
        """Whether the person's meetings are kept; they are until the person says otherwise."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            settings = await session.get(SettingsRecord, principal.user_id)
        return settings is None or settings.keep_meetings

    async def keep_meetings(self, principal: Principal, *, keep: bool) -> bool:
        """Set whether the person's meetings are kept, for the meetings they start from now."""
        now = self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            await session.execute(
                insert(SettingsRecord)
                .values(user_id=principal.user_id, keep_meetings=keep, updated_at=now)
                .on_conflict_do_update(
                    index_elements=[SettingsRecord.user_id],
                    set_={"keep_meetings": keep, "updated_at": now},
                )
            )
        return keep

    async def native_me(self, principal: Principal) -> Mapping[str, object]:
        """The draft's `no_logs` of `/v1/auth/me`."""
        return {"no_logs": not await self.keeps_meetings(principal)}
