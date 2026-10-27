"""The cost settlement hook: a slice's debit for a call, made once with its cost row (F6-C3).

`billing` registers a `CostSettlement` that debits credits for a user's call. The writer runs
every settlement in the cost row's transaction, only when the row is written — a replayed
effect key runs none — so inv-9's "at most one debit" follows from the same insert that
makes one row. A settlement makes no external call (§14 rule 1). A row tells its kind: the
minute rows of a live session (`LIVE_SESSION_KINDS`) are counted by the slice that holds the
session, in the plan's minutes (ADR 0070 LV-D7), not by the tokens they carry.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

# Виды живых сессий порта: их строки пишутся поминутно, а минуты считает срез сессии.
LIVE_SESSION_KINDS: Final = frozenset({"live_transcription", "live_translation", "voice"})


@dataclass(frozen=True, slots=True)
class SettledCost:
    """A recorded cost as a settlement sees it."""

    cost_id: UUID
    user_id: UUID | None
    org_id: UUID | None
    platform_account: str | None
    provider: str
    model: str
    feature: str
    call_class: str
    origin: str
    cost_usd: Decimal
    # Момент строки и её токены (вход с кешированными, выход, аудио): по ним billing ведёт
    # недельные и дневные токены тарифа (BL-D4).
    created_at: datetime
    tokens: int
    # Вид вызова строки: `chat`, `voice`, `live_transcription`…
    kind: str = "chat"

    @property
    def live(self) -> bool:
        """A minute row of a live session: its slice counts its minutes."""
        return self.kind in LIVE_SESSION_KINDS


class CostSettlement(Protocol):
    """A slice's reaction to a recorded cost, run in the cost row's transaction."""

    @property
    def name(self) -> str:
        """The settlement's stable name, for logs."""
        ...

    async def settle(self, session: AsyncSession, cost: SettledCost) -> None:
        """Apply the settlement's effect for this cost in the given session."""
        ...


class CostSettlements:
    """The settlements of the process, installed once by composition after slices are built."""

    def __init__(self) -> None:
        self._installed: tuple[CostSettlement, ...] | None = None

    def install(self, settlements: Sequence[CostSettlement]) -> None:
        """Set the settlements once; a second install is a composition error."""
        if self._installed is not None:
            message = "хуки расчёта стоимости уже установлены"
            raise RuntimeError(message)
        self._installed = tuple(settlements)

    def all(self) -> tuple[CostSettlement, ...]:
        """The installed settlements; none before composition installs them."""
        return self._installed or ()
