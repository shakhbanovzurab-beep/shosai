"""The cost settlement hook: a slice's debit for a call, made once with its cost row (F6-C3).

`billing` registers a `CostSettlement` that debits credits for a user's call. The writer runs
every settlement in the cost row's transaction, only when the row is written — a replayed
effect key runs none — so inv-9's "at most one debit" follows from the same insert that
makes one row. A settlement makes no external call (§14 rule 1).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


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
    cost_usd: Decimal


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
