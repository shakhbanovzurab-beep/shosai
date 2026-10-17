"""The admin's plan catalogue: list, create, change, archive, restore and remove (billing step 2).

The catalogue lives only in the EU home. A plan with subscribers is archived, never
deleted; an archived plan is off sale and cannot be edited until it is restored. A
removed plan leaves every promo code's scope, and a code left with no plan is switched
off. The Free plan stays free, individual and on its slug, and is never archived or
removed: lapsed plans fall back to it (BL-D2). A plan any subscription still names is
archived instead of deleted. After a change commits, cached entitlement snapshots built
on the old catalogue stop being read.
"""

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from http import HTTPStatus
from typing import Final, Protocol
from uuid import UUID

import structlog
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.billing.domain.plans import FREE_PLAN_ID, Audience, Plan
from shosai.features.billing.infrastructure.catalogue_rows import (
    plan_of,
    violates_unique,
    write_plan,
)
from shosai.features.billing.infrastructure.plan_records import TariffRecord
from shosai.features.billing.infrastructure.promo_records import PromoCodeRecord

CATALOGUE_SCOPE: Final = TenancyScope(Home.EU)
SLUG_INDEX: Final = "uq_tariffs_slug"
FREE_SLUG: Final = "free"

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PlanHolding:
    """Who holds a plan: subscribers now, and every subscription record naming it."""

    current: int
    referenced: int


NOBODY: Final = PlanHolding(0, 0)


class PlanSubscribers(Protocol):
    """How many hold each plan, over both homes."""

    async def counts(self, plan_ids: Collection[UUID]) -> Mapping[UUID, PlanHolding]:
        """The holding per plan; a plan nobody holds may be absent."""
        ...


class CatalogueWatcher(Protocol):
    """Told after a change of the catalogue commits."""

    async def catalogue_changed(self) -> None:
        """Stop reading what was derived from the previous catalogue."""
        ...


@dataclass(frozen=True, slots=True)
class CataloguePlan:
    """A plan as the admin sees it."""

    id: UUID
    plan: Plan
    subscribers: int
    created_at: datetime
    updated_at: datetime


class RemovalResult(StrEnum):
    """What removing a plan did."""

    DELETED = "deleted"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class PlanRemoval:
    """The plan archived instead of deleted, or the promo codes the deletion changed."""

    result: RemovalResult
    plan: CataloguePlan | None
    promo_codes_updated: int


def not_found() -> AppError:
    """The plan does not exist."""
    return AppError("plan_not_found", HTTPStatus.NOT_FOUND)


def slug_taken() -> AppError:
    """Another plan holds the slug."""
    return AppError("plan_slug_taken", HTTPStatus.CONFLICT)


def free_plan_locked() -> AppError:
    """The change would stop the Free plan being the plan everyone falls back to."""
    return AppError("free_plan_locked", HTTPStatus.CONFLICT)


def off_sale_when_archived(plan: Plan) -> Plan:
    """An archived plan is never offered nor highlighted."""
    return replace(plan, on_sale=False, featured=False) if plan.archived else plan


def keeps_free_plan(plan: Plan) -> bool:
    """Whether the Free plan stays the fallback plan after a change."""
    return (
        plan.slug == FREE_SLUG and plan.free and not plan.archived
        and plan.audience is Audience.INDIVIDUAL and plan.seats is None
    )  # fmt: skip


class Catalogue:
    """The admin's use cases over the plan catalogue."""

    def __init__(
        self,
        transactions: HomeTransactions,
        holders: tuple[PlanSubscribers, CatalogueWatcher],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._subscribers, self._watcher = holders
        self._clock = clock

    async def plans(self) -> list[CataloguePlan]:
        """Every plan, archived ones included, in the pricing page's order."""
        statement = select(TariffRecord).order_by(
            TariffRecord.sort_order, TariffRecord.name, TariffRecord.id
        )
        async with self._transactions.begin(CATALOGUE_SCOPE, read_only=True) as session:
            rows = (await session.scalars(statement)).all()
        counts = await self._subscribers.counts([row.id for row in rows])
        return [catalogue_plan(row, counts.get(row.id, NOBODY).current) for row in rows]

    async def create(self, plan: Plan) -> CataloguePlan:
        """A new plan on its own slug; it starts unarchived."""
        plan = replace(plan, archived=False)
        now = self._clock()
        row = TariffRecord(id=new_id(), created_at=now)
        write_plan(row, plan, now)
        async with self._transactions.begin(CATALOGUE_SCOPE) as session:
            session.add(row)
            await flush_unique(session)
            await session.refresh(row)
        log.info("Тариф создан", plan_id=str(row.id), slug=plan.slug)
        return catalogue_plan(row, 0)

    async def change(self, plan_id: UUID, edit: Callable[[Plan], Plan]) -> CataloguePlan:
        """Apply the admin's edit; an archived plan only accepts being restored with it."""
        async with self._transactions.begin(CATALOGUE_SCOPE) as session:
            row = await locked(session, plan_id)
            current = plan_of(row)
            changed = off_sale_when_archived(edit(current))
            if current.archived and changed.archived:
                raise AppError("plan_archived", HTTPStatus.CONFLICT)
            if plan_id == FREE_PLAN_ID and not keeps_free_plan(changed):
                raise free_plan_locked()
            write_plan(row, changed, self._clock())
            await flush_unique(session)
            await session.refresh(row)
        await self._watcher.catalogue_changed()
        counts = await self._subscribers.counts([plan_id])
        log.info("Тариф изменён", plan_id=str(plan_id), archived=changed.archived)
        return catalogue_plan(row, counts.get(plan_id, NOBODY).current)

    async def remove(self, plan_id: UUID) -> PlanRemoval:
        """Delete a plan no subscription names, or archive one that is held."""
        if plan_id == FREE_PLAN_ID:
            raise free_plan_locked()
        async with self._transactions.begin(CATALOGUE_SCOPE) as session:
            row = await locked(session, plan_id)
            holding = (await self._subscribers.counts([plan_id])).get(plan_id, NOBODY)
            if holding.referenced > 0:
                removal = await self._archive(session, row, holding.current)
            else:
                await session.execute(delete(TariffRecord).where(TariffRecord.id == plan_id))
                removal = PlanRemoval(
                    RemovalResult.DELETED, None, await leave_promo_scopes(session, plan_id)
                )
        await self._watcher.catalogue_changed()
        if removal.result is RemovalResult.DELETED:
            updated = removal.promo_codes_updated
            log.info("Тариф удалён", plan_id=str(plan_id), promo_codes_updated=updated)
        return removal

    async def _archive(
        self, session: AsyncSession, row: TariffRecord, subscribers: int
    ) -> PlanRemoval:
        current = plan_of(row)
        if current.archived:
            raise AppError("plan_archived_with_subscribers", HTTPStatus.CONFLICT)
        write_plan(row, off_sale_when_archived(replace(current, archived=True)), self._clock())
        await session.flush()
        await session.refresh(row)
        log.info("Тариф с подписчиками ушёл в архив", plan_id=str(row.id))
        return PlanRemoval(RemovalResult.ARCHIVED, catalogue_plan(row, subscribers), 0)


def catalogue_plan(row: TariffRecord, subscribers: int) -> CataloguePlan:
    """The admin's view of a row."""
    return CataloguePlan(row.id, plan_of(row), subscribers, row.created_at, row.updated_at)


async def locked(session: AsyncSession, plan_id: UUID) -> TariffRecord:
    """The plan's row, locked for the rest of the transaction."""
    statement = select(TariffRecord).where(TariffRecord.id == plan_id).with_for_update()
    row = await session.scalar(statement)
    if row is None:
        raise not_found()
    return row


async def flush_unique(session: AsyncSession) -> None:
    """Write the pending row; a slug another plan holds is a conflict, not a crash."""
    try:
        await session.flush()
    except IntegrityError as error:
        if violates_unique(error, SLUG_INDEX):
            raise slug_taken() from error
        raise


async def leave_promo_scopes(session: AsyncSession, plan_id: UUID) -> int:
    """Take a removed plan out of every promo code; a code with no plan left is switched off."""
    remaining = func.array_remove(PromoCodeRecord.plan_ids, plan_id)
    statement = (
        update(PromoCodeRecord)
        .where(PromoCodeRecord.plan_ids.contains([plan_id]))
        .values(
            plan_ids=remaining,
            is_active=case(
                (func.cardinality(remaining) == 0, False), else_=PromoCodeRecord.is_active
            ),
        )
        .returning(PromoCodeRecord.id)
    )
    changed: Sequence[UUID] = (await session.scalars(statement)).all()
    return len(changed)
