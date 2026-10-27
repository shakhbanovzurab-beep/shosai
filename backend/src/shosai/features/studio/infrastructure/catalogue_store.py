"""The catalogue's and the defaults' rows as the domain sees them (studio plan §3.6).

Writes that must agree with each other lock the model rows they read, in id order so two
writers never wait on each other in a circle: a role's new default and a model switched off,
retired or made frontier take the same row locks, and READ COMMITTED lets the second see the
first's result once it commits.
"""

from collections.abc import Collection, Mapping
from datetime import datetime
from types import MappingProxyType

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.studio.domain.catalogue import CatalogueModel
from shosai.features.studio.domain.defaults import RoleDefault
from shosai.features.studio.domain.roles import ModelCapability, ModelRole, Tier
from shosai.features.studio.infrastructure.platform_records import (
    CatalogueRecord,
    RoleDefaultRecord,
)


def model_of(record: CatalogueRecord) -> CatalogueModel:
    """The domain's model of a catalogue row."""
    return CatalogueModel(
        id=record.id,
        openrouter_id=record.openrouter_id,
        name=record.name,
        maker=record.maker,
        context_length=record.context_length,
        max_output_tokens=record.max_output_tokens,
        capabilities=frozenset(ModelCapability(value) for value in record.capabilities),
        supports_temperature=record.supports_temperature,
        supports_reasoning=record.supports_reasoning,
        tier=Tier(record.tier),
        tier_proposed=Tier(record.tier_proposed) if record.tier_proposed else None,
        tier_declined=Tier(record.tier_declined) if record.tier_declined else None,
        enabled=record.enabled,
        retired=record.retired_at is not None,
    )


def record_of(model: CatalogueModel, now: datetime) -> CatalogueRecord:
    """A new catalogue row of the domain's model."""
    record = CatalogueRecord(
        id=model.id,
        openrouter_id=model.openrouter_id,
        tier=model.tier.value,
        tier_confirmed_at=now,
        metadata_synced_at=now,
        added_at=now,
    )
    write(record, model, now)
    return record


def write(record: CatalogueRecord, model: CatalogueModel, now: datetime) -> None:
    """Carry the domain's model into its row; `now` dates what changed."""
    record.name, record.maker = model.name, model.maker
    record.context_length, record.max_output_tokens = model.context_length, model.max_output_tokens
    record.capabilities = sorted(capability.value for capability in model.capabilities)
    record.supports_temperature = model.supports_temperature
    record.supports_reasoning = model.supports_reasoning
    record.enabled = model.enabled
    if record.tier != model.tier.value:
        record.tier_confirmed_at = now
    record.tier = model.tier.value
    proposed = model.tier_proposed.value if model.tier_proposed else None
    if proposed != record.tier_proposed:
        record.tier_proposed_at = now if proposed is not None else None
    record.tier_proposed = proposed
    record.tier_declined = model.tier_declined.value if model.tier_declined else None
    if model.retired and record.retired_at is None:
        record.retired_at = now
    if not model.retired:
        record.retired_at = None
    record.updated_at = now


def default_of(record: RoleDefaultRecord) -> RoleDefault:
    """The domain's default of a role's row."""
    return RoleDefault(ModelRole(record.role), record.model_id, record.fallback_model_id)


async def locked_models(
    session: AsyncSession, model_ids: Collection[str]
) -> Mapping[str, CatalogueRecord]:
    """The rows of these models, locked for the transaction, by id."""
    rows = await session.scalars(
        select(CatalogueRecord)
        .where(CatalogueRecord.id.in_(sorted(set(model_ids))))
        .order_by(CatalogueRecord.id)
        .with_for_update()
    )
    return MappingProxyType({row.id: row for row in rows})


async def role_defaults(session: AsyncSession) -> tuple[RoleDefault, ...]:
    """Every role's default and fallback."""
    rows = await session.scalars(select(RoleDefaultRecord).order_by(RoleDefaultRecord.role))
    return tuple(default_of(row) for row in rows)
