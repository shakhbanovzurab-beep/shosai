"""The admin's promo codes: list, create, change and delete (billing step 2).

Codes live in the EU home beside the catalogue. A code names only plans that exist;
an archived plan may stay in a code that already had it but is never added. The use
count belongs to payments: an edit never writes it and never sets the limit below it.
"""

from collections.abc import Callable, Collection
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.business_calendar import BusinessCalendar
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.features.billing.application.catalogue import CATALOGUE_SCOPE
from shosai.features.billing.domain.promos import PromoCode
from shosai.features.billing.infrastructure.catalogue_rows import (
    promo_of,
    violates_unique,
    write_promo,
)
from shosai.features.billing.infrastructure.plan_records import TariffRecord
from shosai.features.billing.infrastructure.promo_records import PromoCodeRecord

CODE_INDEX: Final = "uq_promo_codes_code"

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CataloguePromo:
    """A promo code as the admin sees it."""

    id: UUID
    promo: PromoCode
    created_at: datetime


def not_found() -> AppError:
    """The promo code does not exist."""
    return AppError("promo_not_found", HTTPStatus.NOT_FOUND)


class PromoCodes:
    """The admin's use cases over promo codes."""

    def __init__(
        self,
        transactions: HomeTransactions,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        *,
        business: BusinessCalendar,
    ) -> None:
        self._transactions = transactions
        self._clock = clock
        self._business = business

    def today(self) -> date:
        """The business date a code's status is judged on (ADR 0058)."""
        return self._business.date_of(self._clock())

    async def codes(self) -> list[CataloguePromo]:
        """Every code, newest first."""
        statement = select(PromoCodeRecord).order_by(
            PromoCodeRecord.created_at.desc(), PromoCodeRecord.id.desc()
        )
        async with self._transactions.begin(CATALOGUE_SCOPE, read_only=True) as session:
            rows = (await session.scalars(statement)).all()
        return [catalogue_promo(row) for row in rows]

    async def create(self, promo: PromoCode) -> CataloguePromo:
        """A new code, unused, on plans that exist and are not archived."""
        promo = replace(promo, redemptions=0)
        row = PromoCodeRecord(id=new_id(), redemptions=0)
        write_promo(row, promo)
        async with self._transactions.begin(CATALOGUE_SCOPE) as session:
            await check_plans(session, promo.plan_ids or (), kept=())
            session.add(row)
            await flush_unique(session)
            await session.refresh(row)
        log.info("Промокод создан", promo_id=str(row.id))
        return catalogue_promo(row)

    async def change(
        self, promo_id: UUID, edit: Callable[[PromoCode], PromoCode]
    ) -> CataloguePromo:
        """Apply the admin's edit to a code; its use count stays as payments left it."""
        async with self._transactions.begin(CATALOGUE_SCOPE) as session:
            row = await session.scalar(
                select(PromoCodeRecord).where(PromoCodeRecord.id == promo_id).with_for_update()
            )
            if row is None:
                raise not_found()
            current = promo_of(row)
            changed = replace(edit(current), redemptions=current.redemptions)
            limit = changed.max_redemptions
            if limit is not None and limit < current.redemptions:
                raise AppError(
                    "promo_limit_below_used",
                    HTTPStatus.UNPROCESSABLE_CONTENT,
                    params={"redemptions": current.redemptions},
                )
            await check_plans(session, changed.plan_ids or (), kept=current.plan_ids or ())
            write_promo(row, changed)
            await flush_unique(session)
            await session.refresh(row)
        log.info("Промокод изменён", promo_id=str(promo_id), active=changed.active)
        return catalogue_promo(row)

    async def remove(self, promo_id: UUID) -> None:
        """Delete a code."""
        async with self._transactions.begin(CATALOGUE_SCOPE) as session:
            removed = await session.scalar(
                delete(PromoCodeRecord)
                .where(PromoCodeRecord.id == promo_id)
                .returning(PromoCodeRecord.id)
            )
        if removed is None:
            raise not_found()
        log.info("Промокод удалён", promo_id=str(promo_id))


def catalogue_promo(row: PromoCodeRecord) -> CataloguePromo:
    """The admin's view of a row."""
    return CataloguePromo(row.id, promo_of(row), row.created_at)


async def check_plans(
    session: AsyncSession, plan_ids: Collection[UUID], kept: Collection[UUID]
) -> None:
    """Every plan exists, held against removal until commit; an archived one only if kept."""
    if not plan_ids:
        return
    statement = (
        select(TariffRecord.id, TariffRecord.archived_at)
        .where(TariffRecord.id.in_(list(plan_ids)))
        .with_for_update(read=True)
    )
    found = {row.id: row.archived_at for row in (await session.execute(statement)).all()}
    if set(plan_ids) - set(found):
        raise AppError("promo_plan_unknown", HTTPStatus.UNPROCESSABLE_CONTENT)
    if any(found[plan] is not None and plan not in kept for plan in plan_ids):
        raise AppError("promo_plan_archived", HTTPStatus.UNPROCESSABLE_CONTENT)


async def flush_unique(session: AsyncSession) -> None:
    """Write the pending row; a code that already exists is a conflict, not a crash."""
    try:
        await session.flush()
    except IntegrityError as error:
        if violates_unique(error, CODE_INDEX):
            raise AppError("promo_code_taken", HTTPStatus.CONFLICT) from error
        raise
