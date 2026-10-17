"""An entitlement entry from the person's subscription and the catalogue, at a moment.

Pure: the rows are already read. The plan in force follows the domain's time rules; the
card shows the plan the subscription bought, whatever is in force now.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shosai.features.billing.application.entitlement_entries import (
    EntitlementEntry,
    SubscriptionCard,
)
from shosai.features.billing.contracts import EntitlementSnapshot, EntitlementSource
from shosai.features.billing.domain.entitlements import (
    QueuedPlan,
    SubscriptionFacts,
    entitled,
    next_change,
)
from shosai.features.billing.domain.plans import (
    FREE_PLAN_ID,
    BillingPeriod,
    Capability,
    Plan,
)


@dataclass(frozen=True, slots=True)
class SubscriptionRow:
    """The subscription as its home stores it."""

    plan_id: UUID
    billing_period: BillingPeriod | None
    started_at: datetime
    expires_at: datetime | None
    auto_renew: bool
    trial: bool
    version: int


@dataclass(frozen=True, slots=True)
class QueuedRow:
    """A queued plan as its home stores it, in queue order."""

    plan_id: UUID
    days: int


class UnknownPlanError(LookupError):
    """A subscription names a plan the catalogue does not have."""


def build_entry(
    user_id: UUID,
    held: tuple[SubscriptionRow | None, Sequence[QueuedRow]],
    plans: Mapping[UUID, Plan],
    at: tuple[datetime, str],
) -> EntitlementEntry:
    """The person's entry at `now`, built on the catalogue of mark `catalogue`."""
    row, queue = held
    now, catalogue = at
    facts = None if row is None else facts_of(row, queue, plans)
    got = entitled(facts, plan_named(plans, FREE_PLAN_ID), now)
    plan = got.plan
    snapshot = EntitlementSnapshot(
        user_id=user_id, plan_slug=plan.slug, plan_name=plan.name, audience=plan.audience,
        paid=got.paid, in_grace=got.in_grace, paid_until=got.paid_until, limits=plan.limits,
        capabilities=plan.capabilities, source=EntitlementSource.PERSONAL, workspace_id=None,
        version=0 if row is None else row.version,
    )  # fmt: skip
    card = None if row is None else card_of(row, plan_named(plans, row.plan_id))
    return EntitlementEntry(snapshot, card, next_change(facts, now), catalogue)


def facts_of(
    row: SubscriptionRow, queue: Sequence[QueuedRow], plans: Mapping[UUID, Plan]
) -> SubscriptionFacts:
    """The rules' view of the stored subscription."""
    return SubscriptionFacts(
        plan=plan_named(plans, row.plan_id),
        expires_at=row.expires_at,
        auto_renew=row.auto_renew,
        trial=row.trial,
        queued=tuple(QueuedPlan(plan_named(plans, item.plan_id), item.days) for item in queue),
    )


def card_of(row: SubscriptionRow, plan: Plan) -> SubscriptionCard:
    """The native card of the plan the subscription bought."""
    period = row.billing_period or BillingPeriod.MONTH
    limits = plan.limits
    return SubscriptionCard(
        plan_id=row.plan_id, slug=plan.slug, name=plan.name,
        prices=dict(plan.prices[period].amounts), billing_period=row.billing_period,
        minutes_limit=limits.meeting_minutes_per_month,
        knowledge_base_mb=limits.knowledge_base_mb, file_manager_gb=limits.file_manager_gb,
        frontier_models=Capability.FRONTIER_MODELS in plan.capabilities, on_sale=plan.on_sale,
        started_at=row.started_at, expires_at=row.expires_at,
    )  # fmt: skip


def plan_named(plans: Mapping[UUID, Plan], plan_id: UUID) -> Plan:
    """The catalogue's plan; a missing one is a broken reference, never a guess."""
    plan = plans.get(plan_id)
    if plan is None:
        raise UnknownPlanError(str(plan_id))
    return plan
