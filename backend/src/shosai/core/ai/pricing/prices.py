"""The prices in force, read from the EU home and cached 60 s per process (ADR 0035).

Every call needs the prices of its model before it is sent: for the reservation estimate,
and for the cost of a call whose provider reports no money. A model without a price for each
unit its kind needs is refused (`model_unpriced`) — never metered at $0.
"""

import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on

from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.pricing.records import ProviderPrice
from shosai.core.ai.results import Unit
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope

PRICES_TTL: Final = timedelta(seconds=60)

type ModelPrices = Mapping[Unit, Decimal]

IN_FORCE = (
    select(ProviderPrice.provider, ProviderPrice.model, ProviderPrice.unit, ProviderPrice.price_usd)
    .ext(distinct_on(ProviderPrice.provider, ProviderPrice.model, ProviderPrice.unit))
    .where(ProviderPrice.effective_from <= func.now())
    .order_by(
        ProviderPrice.provider,
        ProviderPrice.model,
        ProviderPrice.unit,
        ProviderPrice.effective_from.desc(),
    )
)


@dataclass(frozen=True, slots=True)
class _Snapshot:
    prices: Mapping[ModelRef, ModelPrices]
    taken_at: float


class PriceBook:
    """The prices of every model in force, refreshed at most once a minute per process."""

    def __init__(self, transactions: HomeTransactions, ttl: timedelta = PRICES_TTL) -> None:
        self._transactions = transactions
        self._ttl = ttl.total_seconds()
        self._snapshot: _Snapshot | None = None
        self._lock = asyncio.Lock()

    async def prices_of(self, model: ModelRef) -> ModelPrices:
        """The unit prices of the model; empty when it has none."""
        snapshot = await self._current()
        return snapshot.prices.get(model, MappingProxyType({}))

    async def _current(self) -> _Snapshot:
        snapshot = self._snapshot
        if snapshot is not None and time.monotonic() - snapshot.taken_at < self._ttl:
            return snapshot
        # Один процесс — одно чтение: остальные ждут его, а не идут в базу вслед.
        async with self._lock:
            snapshot = self._snapshot
            if snapshot is None or time.monotonic() - snapshot.taken_at >= self._ttl:
                snapshot = await self._read()
                self._snapshot = snapshot
        return snapshot

    async def _read(self) -> _Snapshot:
        async with self._transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
            rows = (await session.execute(IN_FORCE)).all()
        prices: dict[ModelRef, dict[Unit, Decimal]] = {}
        for provider, model, unit, price in rows:
            ref = ModelRef(Provider(provider), model)
            prices.setdefault(ref, {})[Unit(unit)] = price
        return _Snapshot(
            prices=MappingProxyType(
                {ref: MappingProxyType(units) for ref, units in prices.items()}
            ),
            taken_at=time.monotonic(),
        )
