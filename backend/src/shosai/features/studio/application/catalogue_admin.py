"""What the operator does to the catalogue (studio plan §3.5, ST-D3, ST-D4, ADR 0074).

A model is added by its OpenRouter id, described by OpenRouter's list, in the tier the
operator confirms — the one its price proposes unless they choose — and switched off until
switched on. A model a role's default or fallback holds cannot be switched off, retired or
made frontier; a default is switched on, standard and capable of its role. Every write locks
the model rows it reads, so two writes never leave a default the rules refuse. Switching a
model off tells the monitoring chat; this process's snapshot is dropped after each write.
"""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.listing import ListedModel, ModelListing, ModelListUnavailableError
from shosai.core.ai.results import Unit
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.studio.contracts.events import DisabledBy, ModelDisabled
from shosai.features.studio.domain.catalogue import (
    CatalogueModel,
    Listing,
    confirmed,
    declined,
    hashed_slug,
    listed,
    priced_tier,
)
from shosai.features.studio.domain.defaults import RoleDefault, checked_default, held_by
from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.roles import ModelRole, Tier
from shosai.features.studio.infrastructure.catalogue_store import (
    default_of,
    locked_models,
    model_of,
    record_of,
    role_defaults,
    write,
)
from shosai.features.studio.infrastructure.platform_records import (
    CatalogueRecord,
    RoleDefaultRecord,
)
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot

EU = TenancyScope(Home.EU)


def listing_of(model: ListedModel) -> Listing:
    """The domain's listing of what OpenRouter says."""
    return Listing(
        openrouter_id=model.id,
        name=model.name,
        context_length=model.context_length,
        max_output_tokens=model.max_output_tokens,
        input_modalities=model.input_modalities,
        output_modalities=model.output_modalities,
        parameters=model.parameters,
    )


class CatalogueAdmin:
    """The catalogue and the defaults, changed by the operator."""

    def __init__(
        self,
        transactions: HomeTransactions,
        sources: tuple[ModelListing, EventOutbox, PlatformSnapshot],
        line_usd_per_million: Decimal,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._listing, self._outbox, self._snapshot = sources
        self._line = line_usd_per_million
        self._clock = clock

    async def priced(self, openrouter_id: str) -> Tier | None:
        """The tier the model's output price in force proposes; none without a price."""
        prices = await self._listing.prices.prices_of(ModelRef(Provider.OPENROUTER, openrouter_id))
        return priced_tier(prices.get(Unit.OUTPUT), self._line)

    async def add(self, openrouter_id: str, tier: Tier | None = None) -> CatalogueModel:
        """List a model OpenRouter lists, switched off; a retired one comes back."""
        try:
            found = (await self._listing.openrouter.listed()).get(openrouter_id)
        except ModelListUnavailableError as error:
            raise StudioRuleError(StudioRule.OPENROUTER_UNREACHABLE) from error
        if found is None:
            raise StudioRuleError(StudioRule.MODEL_NOT_ON_OPENROUTER)
        chosen = tier or await self.priced(openrouter_id) or Tier.STANDARD
        model, now = listed(listing_of(found), chosen), self._clock()
        async with self._transactions.begin(EU) as session:
            existing = await session.scalar(
                select(CatalogueRecord)
                .where(CatalogueRecord.openrouter_id == openrouter_id)
                .with_for_update()
            )
            if existing is not None and existing.retired_at is None:
                raise StudioRuleError(StudioRule.MODEL_ALREADY_LISTED)
            if existing is not None:
                write(existing, replace(model, id=existing.id), now)
            elif await session.get(CatalogueRecord, model.id) is None:
                session.add(record_of(model, now))
            else:
                model = replace(model, id=hashed_slug(openrouter_id))
                session.add(record_of(model, now))
        self._snapshot.drop()
        return model

    async def switch(self, model_id: str, *, enabled: bool) -> CatalogueModel:
        """Switch a model on or off; a model a default holds stays on."""
        async with self._transactions.begin(EU) as session:
            record = await self._listed(session, model_id)
            model = model_of(record)
            if not enabled and held_by(model_id, await role_defaults(session)):
                raise StudioRuleError(StudioRule.MODEL_IS_DEFAULT)
            changed = replace(model, enabled=enabled)
            write(record, changed, self._clock())
            if model.enabled and not enabled:
                await self._outbox.add(
                    session, ModelDisabled(model_id=model_id, reason=DisabledBy.ADMIN)
                )
        self._snapshot.drop()
        return changed

    async def retire(self, model_id: str) -> None:
        """Take a switched-off model no role uses out of the catalogue, for good."""
        async with self._transactions.begin(EU) as session:
            record = await self._listed(session, model_id)
            if record.enabled:
                raise StudioRuleError(StudioRule.MODEL_ENABLED)
            if held_by(model_id, await role_defaults(session)):
                raise StudioRuleError(StudioRule.MODEL_IS_DEFAULT)
            write(record, replace(model_of(record), retired=True), self._clock())
        self._snapshot.drop()

    async def decide_tier(self, model_id: str, *, confirm: bool) -> CatalogueModel:
        """Confirm or decline the tier the model's price proposes; it counts from now."""
        async with self._transactions.begin(EU) as session:
            record = await self._listed(session, model_id)
            model = model_of(record)
            if model.tier_proposed is None:
                raise StudioRuleError(StudioRule.NO_TIER_PROPOSAL)
            frontier = confirm and model.tier_proposed is Tier.FRONTIER
            if frontier and held_by(model_id, await role_defaults(session)):
                raise StudioRuleError(StudioRule.MODEL_IS_DEFAULT)
            changed = confirmed(model) if confirm else declined(model)
            write(record, changed, self._clock())
        self._snapshot.drop()
        return changed

    async def set_default(
        self, role: ModelRole, model_id: str, fallback_id: str | None = None
    ) -> RoleDefault:
        """A role's new default and fallback, each checked under its row's lock."""
        ids = {model_id} if fallback_id is None else {model_id, fallback_id}
        async with self._transactions.begin(EU) as session:
            rows = await locked_models(session, ids)
            model, fallback = rows.get(model_id), rows.get(fallback_id) if fallback_id else None
            default = checked_default(
                role,
                model_of(model) if model is not None else None,
                fallback_id,
                model_of(fallback) if fallback is not None else None,
            )
            values = {
                "role": role.value,
                "model_id": default.model_id,
                "fallback_model_id": default.fallback_id,
                "updated_at": self._clock(),
            }
            statement = insert(RoleDefaultRecord).values(values)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[RoleDefaultRecord.role], set_=values
                )
            )
        self._snapshot.drop()
        return default

    async def defaults(self) -> tuple[RoleDefault, ...]:
        """Every role's default and fallback, as stored."""
        async with self._transactions.begin(EU, read_only=True) as session:
            rows = await session.scalars(select(RoleDefaultRecord).order_by(RoleDefaultRecord.role))
            return tuple(default_of(row) for row in rows)

    @staticmethod
    async def _listed(session: AsyncSession, model_id: str) -> CatalogueRecord:
        """The model's row, locked; a retired or unknown model is not found."""
        record = (await locked_models(session, (model_id,))).get(model_id)
        if record is None or record.retired_at is not None:
            raise StudioRuleError(StudioRule.MODEL_NOT_FOUND)
        return record
