"""Recording a person's subscription: the one way any step changes what a person holds.

The change runs in the caller's transaction: the subscription row is written with its
version raised, the queue is replaced, `billing.subscription.changed` joins the outbox,
and the cached snapshot's floor is raised to the new version before the commit, so the
next read after the commit sees the change (billing step 3).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, func, insert
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.ids import new_id
from shosai.features.billing.contracts.events import SubscriptionChanged
from shosai.features.billing.domain.plans import BillingPeriod
from shosai.features.billing.infrastructure.subscription_records import (
    SubscriptionRecord,
    SubscriptionSegmentRecord,
)


@dataclass(frozen=True, slots=True)
class PlanRef:
    """A plan of the catalogue by id, with the slug the event carries."""

    id: UUID
    slug: str


@dataclass(frozen=True, slots=True)
class SubscriptionTerms:
    """What the person holds after the change."""

    plan: PlanRef
    billing_period: BillingPeriod | None
    started_at: datetime
    expires_at: datetime | None
    auto_renew: bool = False
    trial: bool = False
    # Тарифы в очереди за действующим, по порядку: тариф и оставшиеся дни.
    queued: tuple[tuple[UUID, int], ...] = ()


class VersionFloor(Protocol):
    """The cache's guard against snapshots older than a change."""

    async def raise_floor(self, user_id: UUID, version: int) -> bool:
        """Drop the person's snapshot and refuse older ones."""
        ...


class SubscriptionLedger:
    """Writes subscriptions with their version, event and cache floor."""

    def __init__(self, outbox: EventOutbox, floor: VersionFloor) -> None:
        self._outbox = outbox
        self._floor = floor

    async def record(self, session: AsyncSession, user_id: UUID, terms: SubscriptionTerms) -> int:
        """Write the person's subscription in the caller's transaction; the new version."""
        values = {
            "plan_id": terms.plan.id,
            "billing_period": None if terms.billing_period is None else terms.billing_period.value,
            "started_at": terms.started_at,
            "expires_at": terms.expires_at,
            "auto_renew": terms.auto_renew,
            "trial": terms.trial,
        }
        statement = (
            upsert(SubscriptionRecord)
            .values(id=new_id(), user_id=user_id, **values)
            .on_conflict_do_update(
                index_elements=[SubscriptionRecord.user_id],
                set_={
                    **values,
                    "version": SubscriptionRecord.version + 1,
                    "updated_at": func.now(),
                },
            )
            .returning(SubscriptionRecord.id, SubscriptionRecord.version)
        )
        subscription_id, version = (await session.execute(statement)).one()
        await session.execute(
            delete(SubscriptionSegmentRecord).where(SubscriptionSegmentRecord.user_id == user_id)
        )
        if terms.queued:
            await session.execute(
                insert(SubscriptionSegmentRecord),
                [
                    {
                        "id": new_id(),
                        "user_id": user_id,
                        "plan_id": plan_id,
                        "position": position,
                        "remaining_days": days,
                    }
                    for position, (plan_id, days) in enumerate(terms.queued, start=1)
                ],
            )
        event = SubscriptionChanged(
            subscription_id=subscription_id,
            user_id=user_id,
            plan_slug=terms.plan.slug,
            paid_until=terms.expires_at,
        )
        await self._outbox.add(session, event)
        await self._floor.raise_floor(user_id, version)
        return int(version)
