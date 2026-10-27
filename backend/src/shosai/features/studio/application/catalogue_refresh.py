"""The catalogue's daily refresh from OpenRouter's list (ST-D4 as amended, ADR 0074).

Each listed model takes what the list says of it now, and its output price in force may
propose another tier, which waits for the admin and is reported once. A model the list no
longer has is switched off and reported, unless a role's default or fallback holds it: that
one stays on and is counted every day, as is a default whose model cannot serve its role any
more and a proposal waiting over three days. A list that misses a fifth of the catalogue (at
least three models) is a fault of the list, not news: it switches nothing off. A model back on
the list is not switched on again — the admin decides.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.listing import ListedModel, ModelListing, ModelListUnavailableError
from shosai.core.ai.results import Unit
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.features.studio.application.catalogue_admin import EU, listing_of
from shosai.features.studio.contracts.events import DisabledBy, ModelDisabled, ModelTierProposed
from shosai.features.studio.domain.catalogue import CatalogueModel, described, priced_tier, proposed
from shosai.features.studio.domain.defaults import RoleDefault, held_by
from shosai.features.studio.domain.roles import DEFAULT_REQUIRED, Tier
from shosai.features.studio.infrastructure.catalogue_store import model_of, role_defaults, write
from shosai.features.studio.infrastructure.metrics import (
    BrokenDefault,
    RefreshOutcome,
    StudioMetrics,
)
from shosai.features.studio.infrastructure.platform_records import CatalogueRecord
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot

FUSE_SHARE: Final = Decimal("0.2")
FUSE_MINIMUM: Final = 3
PROPOSAL_WAIT: Final = timedelta(days=3)
log = structlog.stdlib.get_logger(__name__)

LIVE: Final = (
    select(CatalogueRecord).where(CatalogueRecord.retired_at.is_(None)).order_by(CatalogueRecord.id)
)


def fused(missing: int, listed: int) -> bool:
    """Whether a list misses too much of the catalogue to be believed."""
    return missing >= FUSE_MINIMUM and missing > FUSE_SHARE * listed


def unable(defaults: Sequence[RoleDefault], models: Mapping[str, CatalogueModel]) -> int:
    """The defaults and fallbacks whose model cannot serve their role."""
    return sum(
        1
        for default in defaults
        for model_id in default.model_ids
        if (model := models.get(model_id)) is None
        or not model.usable
        or model.tier is not Tier.STANDARD
        or not model.can(DEFAULT_REQUIRED[default.role])
    )


class CatalogueRefresh:
    """The daily refresh of the EU home's catalogue."""

    def __init__(
        self,
        transactions: HomeTransactions,
        sources: tuple[ModelListing, EventOutbox, PlatformSnapshot, StudioMetrics],
        line_usd_per_million: Decimal,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._listing, self._outbox, self._snapshot, self._metrics = sources
        self._line = line_usd_per_million
        self._clock = clock

    async def refresh(self) -> RefreshOutcome:
        """Refresh every live model of the catalogue from OpenRouter's list."""
        try:
            listed = await self._listing.openrouter.listed()
        except ModelListUnavailableError:
            self._metrics.refreshed(RefreshOutcome.UNREADABLE)
            return RefreshOutcome.UNREADABLE
        priced = await self._priced()
        async with self._transactions.begin(EU) as session:
            outcome = await self._apply(session, listed, priced)
        self._snapshot.drop()
        self._metrics.refreshed(outcome)
        log.info("Каталог моделей сверен со списком OpenRouter", outcome=outcome.value)
        return outcome

    async def _priced(self) -> dict[str, Tier | None]:
        """The tier each live model's output price proposes, read before the write."""
        async with self._transactions.begin(EU, read_only=True) as session:
            ids = (await session.scalars(select(CatalogueRecord.openrouter_id))).all()
        priced: dict[str, Tier | None] = {}
        for openrouter_id in ids:
            prices = await self._listing.prices.prices_of(
                ModelRef(Provider.OPENROUTER, openrouter_id)
            )
            priced[openrouter_id] = priced_tier(prices.get(Unit.OUTPUT), self._line)
        return priced

    async def _apply(
        self,
        session: AsyncSession,
        listed: Mapping[str, ListedModel],
        priced: Mapping[str, Tier | None],
    ) -> RefreshOutcome:
        rows = (await session.scalars(LIVE.with_for_update())).all()
        defaults = await role_defaults(session)
        missing = [row for row in rows if row.openrouter_id not in listed]
        trust = not fused(len(missing), len(rows))
        if not trust:
            log.error(
                "Список OpenRouter без доли каталога: модели не выключаются", missing=len(missing)
            )
        now = self._clock()
        held_unlisted = 0
        for row in rows:
            entry = listed.get(row.openrouter_id)
            if entry is None:
                held = held_by(row.id, defaults)
                held_unlisted += int(held)
                if trust:
                    await self._unlisted(session, row, now, held=held)
                continue
            await self._listed(session, row, entry, priced.get(row.openrouter_id), now)
        models = {row.id: model_of(row) for row in rows}
        self._metrics.broken(BrokenDefault.UNLISTED, held_unlisted)
        self._metrics.broken(BrokenDefault.CANNOT_SERVE, unable(defaults, models))
        stale = now - PROPOSAL_WAIT
        waiting = sum(
            1 for row in rows if row.tier_proposed_at is not None and row.tier_proposed_at < stale
        )
        self._metrics.waiting(waiting)
        return RefreshOutcome.DONE if trust else RefreshOutcome.FUSED

    async def _listed(
        self,
        session: AsyncSession,
        row: CatalogueRecord,
        entry: ListedModel,
        priced: Tier | None,
        now: datetime,
    ) -> None:
        """A model still listed: its description now and the tier its price proposes."""
        before = model_of(row)
        after = proposed(described(before, listing_of(entry)), priced)
        write(row, after, now)
        row.metadata_synced_at, row.upstream_missing_since = now, None
        if after.tier_proposed is not None and after.tier_proposed != before.tier_proposed:
            event = ModelTierProposed(
                model_id=row.id, confirmed=after.tier, proposed=after.tier_proposed
            )
            await self._outbox.add(session, event)

    async def _unlisted(
        self, session: AsyncSession, row: CatalogueRecord, now: datetime, *, held: bool
    ) -> None:
        """A model the list no longer has: switched off and reported, unless a default holds it."""
        row.upstream_missing_since = row.upstream_missing_since or now
        if held or not row.enabled:
            return
        write(row, replace(model_of(row), enabled=False), now)
        await self._outbox.add(session, ModelDisabled(model_id=row.id, reason=DisabledBy.UPSTREAM))
