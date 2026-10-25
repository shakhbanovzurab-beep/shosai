"""Evaluation cases leave when their reason does (ADR 0068 AG-D13; agent step 11a).

A withdrawn "Help improve the models" consent (`identity.consent.changed`) erases the person's
cases in the delivery's transaction. The daily purge erases every case past its year: the sweep
role lists the people who have one, and each person's go in their own transaction, a batch a
pass. The ratings stay; they no longer share. A removed rating, a deleted thread or account
take their cases by the database's cascade.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.domain.feedback import CASE_RETENTION
from shosai.features.agent.infrastructure.person_records import (
    AgentEvalCaseRecord,
    AgentFeedbackRecord,
)
from shosai.features.identity.contracts import ConsentChanged

CASE = AgentEvalCaseRecord
FEEDBACK = AgentFeedbackRecord
IMPROVE_MODELS: Final = "improve_models"
# Людей за проход: следующий проход берёт остальных.
BATCH: Final = 200
log = structlog.stdlib.get_logger(__name__)


async def erase_cases(session: AsyncSession, user_id: UUID, before: datetime | None = None) -> int:
    """The person's cases, or those made before the moment, erased; how many went."""
    statement = delete(CASE).where(CASE.user_id == user_id)
    if before is not None:
        statement = statement.where(CASE.created_at < before)
    gone = list(await session.scalars(statement.returning(CASE.message_id)))
    if gone:
        await session.execute(
            update(FEEDBACK).where(FEEDBACK.message_id.in_(gone)).values(shared=False)
        )
    return len(gone)


async def consent_changed(session: AsyncSession, event: ConsentChanged) -> None:
    """A withdrawn consent to improve the models takes the person's cases."""
    if event.kind == IMPROVE_MODELS and not event.granted:
        await erase_cases(session, event.user_id)


class CasePurge:
    """The daily purge of cases past their year."""

    def __init__(
        self,
        transactions: HomeTransactions,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._clock = clock

    async def purge(self, home: Home) -> int:
        """Erase the home's cases past their year; how many went."""
        before = self._clock() - CASE_RETENTION
        due = select(CASE.user_id).where(CASE.created_at < before).distinct().limit(BATCH)
        async with self._transactions.begin(
            TenancyScope(home), read_only=True, sweep=True
        ) as session:
            people = list(await session.scalars(due))
        erased = 0
        for user_id in people:
            async with self._transactions.begin(TenancyScope(home, user_id)) as session:
                erased += await erase_cases(session, user_id, before)
        if erased:
            log.info("Оценочные случаи старше года стёрты", home=home.value, cases=erased)
        return erased
