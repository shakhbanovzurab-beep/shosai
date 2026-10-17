"""An entitlement entry as JSON in Valkey, and back.

The shape is versioned by the key's namespace (`entitlement.v1`): a release that changes
it takes a new namespace instead of reading entries the previous release wrote.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from shosai.features.billing.application.entitlement_entries import (
    EntitlementEntry,
    SubscriptionCard,
)
from shosai.features.billing.contracts import EntitlementSnapshot, EntitlementSource
from shosai.features.billing.domain.money import Currency
from shosai.features.billing.domain.plans import (
    Audience,
    BillingPeriod,
    Capability,
    ModelTier,
    PlanLimits,
)


class LimitsJson(BaseModel):
    """A plan's limits."""

    meeting_minutes_per_month: int | None
    file_manager_gb: int | None
    knowledge_base_mb: int | None
    weekly_tokens: dict[ModelTier, int | None]
    daily_standard_tokens: int | None


class SnapshotJson(BaseModel):
    """The contract's snapshot."""

    user_id: UUID
    plan_slug: str
    plan_name: str
    audience: Audience
    paid: bool
    in_grace: bool
    paid_until: datetime | None
    limits: LimitsJson
    capabilities: list[Capability]
    source: EntitlementSource
    workspace_id: UUID | None
    version: int


class CardJson(BaseModel):
    """The native subscription card."""

    plan_id: UUID
    slug: str
    name: str
    prices: dict[Currency, int]
    billing_period: BillingPeriod | None
    minutes_limit: int | None
    knowledge_base_mb: int | None
    file_manager_gb: int | None
    frontier_models: bool
    on_sale: bool
    started_at: datetime
    expires_at: datetime | None


class EntryJson(BaseModel):
    """A whole entry."""

    snapshot: SnapshotJson
    card: CardJson | None
    valid_until: datetime | None
    catalogue: str


def encode(entry: EntitlementEntry) -> bytes:
    """The entry's JSON."""
    snapshot, limits = entry.snapshot, entry.snapshot.limits
    card = entry.card
    return EntryJson(
        snapshot=SnapshotJson(
            user_id=snapshot.user_id, plan_slug=snapshot.plan_slug, plan_name=snapshot.plan_name,
            audience=snapshot.audience, paid=snapshot.paid, in_grace=snapshot.in_grace,
            paid_until=snapshot.paid_until,
            limits=LimitsJson(
                meeting_minutes_per_month=limits.meeting_minutes_per_month,
                file_manager_gb=limits.file_manager_gb, knowledge_base_mb=limits.knowledge_base_mb,
                weekly_tokens=dict(limits.weekly_tokens),
                daily_standard_tokens=limits.daily_standard_tokens,
            ),
            capabilities=sorted(snapshot.capabilities), source=snapshot.source,
            workspace_id=snapshot.workspace_id, version=snapshot.version,
        ),
        card=None if card is None else CardJson(
            plan_id=card.plan_id, slug=card.slug, name=card.name,
            prices=dict(card.prices), billing_period=card.billing_period,
            minutes_limit=card.minutes_limit, knowledge_base_mb=card.knowledge_base_mb,
            file_manager_gb=card.file_manager_gb, frontier_models=card.frontier_models,
            on_sale=card.on_sale, started_at=card.started_at, expires_at=card.expires_at,
        ),
        valid_until=entry.valid_until, catalogue=entry.catalogue,
    ).model_dump_json().encode()  # fmt: skip


def decode(raw: bytes) -> EntitlementEntry:
    """The entry of its JSON; a malformed value raises `ValueError`."""
    data = EntryJson.model_validate_json(raw)
    snapshot, limits, card = data.snapshot, data.snapshot.limits, data.card
    return EntitlementEntry(
        snapshot=EntitlementSnapshot(
            user_id=snapshot.user_id, plan_slug=snapshot.plan_slug, plan_name=snapshot.plan_name,
            audience=snapshot.audience, paid=snapshot.paid, in_grace=snapshot.in_grace,
            paid_until=snapshot.paid_until,
            limits=PlanLimits(
                meeting_minutes_per_month=limits.meeting_minutes_per_month,
                file_manager_gb=limits.file_manager_gb, knowledge_base_mb=limits.knowledge_base_mb,
                weekly_tokens=limits.weekly_tokens,
                daily_standard_tokens=limits.daily_standard_tokens,
            ),
            capabilities=frozenset(snapshot.capabilities), source=snapshot.source,
            workspace_id=snapshot.workspace_id, version=snapshot.version,
        ),
        card=None if card is None else SubscriptionCard(
            plan_id=card.plan_id, slug=card.slug, name=card.name,
            prices=card.prices, billing_period=card.billing_period,
            minutes_limit=card.minutes_limit, knowledge_base_mb=card.knowledge_base_mb,
            file_manager_gb=card.file_manager_gb, frontier_models=card.frontier_models,
            on_sale=card.on_sale, started_at=card.started_at, expires_at=card.expires_at,
        ),
        valid_until=data.valid_until, catalogue=data.catalogue,
    )  # fmt: skip
