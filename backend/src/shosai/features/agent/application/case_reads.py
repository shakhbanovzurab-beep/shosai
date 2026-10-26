"""Leo's evaluation cases read where they live, on the host (ADR 0068 AG-D13; agent step 11c).

The counts are by home, rating, language and model only — no text, no person — and need no
record. The sweep role lists which cases there are. A case's content is read only in the
person's own transaction, together with a row of the admin's audit log naming the case
(`eval_case_read`), so no case is shown or replayed without a trace.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import func, select

from shosai.core.account_data.handlers import AccountRef
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.case_replay import StoredCase
from shosai.features.agent.domain.feedback import Rating
from shosai.features.agent.infrastructure.person_records import AgentEvalCaseRecord
from shosai.features.identity.contracts import OPERATOR_AUDIT, OperatorAction

CASE = AgentEvalCaseRecord
# Модель хода до записи модели: без названия.
NO_MODEL: Final = "unknown"


@dataclass(frozen=True, slots=True)
class CaseCount:
    """How many cases a home keeps of one rating, language and model."""

    home: Home
    rating: Rating
    language: str
    model: str
    cases: int


@dataclass(frozen=True, slots=True)
class CaseRef:
    """A case by its home, person and id — nothing of its content."""

    home: Home
    user_id: UUID
    case_id: UUID


class CaseReads:
    """Counts, lists and reads cases; every read leaves an audit row."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def counts(self) -> list[CaseCount]:
        """The cases of both homes by rating, language and model."""
        found: list[CaseCount] = []
        statement = (
            select(CASE.rating, CASE.language, CASE.model, func.count())
            .group_by(CASE.rating, CASE.language, CASE.model)
            .order_by(CASE.rating, CASE.language, CASE.model)
        )
        for home in Home:
            async with self._transactions.begin(
                TenancyScope(home), read_only=True, sweep=True
            ) as session:
                rows = (await session.execute(statement)).all()
            found += [
                CaseCount(home, Rating(rating), language, model or NO_MODEL, count)
                for rating, language, model, count in rows
            ]
        return found

    async def refs(self, rating: Rating | None, language: str | None, limit: int) -> list[CaseRef]:
        """The newest cases of both homes, as references, at most `limit`."""
        statement = select(CASE.user_id, CASE.id, CASE.created_at).order_by(
            CASE.created_at.desc(), CASE.id.desc()
        )
        if rating is not None:
            statement = statement.where(CASE.rating == rating.value)
        if language is not None:
            statement = statement.where(CASE.language == language)
        found: list[tuple[datetime, CaseRef]] = []
        for home in Home:
            async with self._transactions.begin(
                TenancyScope(home), read_only=True, sweep=True
            ) as session:
                rows = (await session.execute(statement.limit(limit))).all()
            found += [(at, CaseRef(home, user_id, case_id)) for user_id, case_id, at in rows]
        found.sort(key=lambda pair: pair[0], reverse=True)
        return [ref for _, ref in found[:limit]]

    async def find(self, case_id: UUID) -> CaseRef | None:
        """The case by id, in whichever home keeps it."""
        for home in Home:
            async with self._transactions.begin(
                TenancyScope(home), read_only=True, sweep=True
            ) as session:
                user_id = await session.scalar(select(CASE.user_id).where(CASE.id == case_id))
            if user_id is not None:
                return CaseRef(home, user_id, case_id)
        return None

    async def read(self, ref: CaseRef) -> StoredCase | None:
        """The case's content, read in the person's transaction with its audit row; None when
        it went meanwhile."""
        async with self._transactions.begin(TenancyScope(ref.home, ref.user_id)) as session:
            record = await session.scalar(
                select(CASE).where(CASE.id == ref.case_id, CASE.user_id == ref.user_id)
            )
            if record is None:
                return None
            await self._ports.get(OPERATOR_AUDIT).acted(
                session, AccountRef(ref.user_id, ref.home), OperatorAction.EVAL_CASE_READ, record.id
            )
            return StoredCase(record.id, Rating(record.rating), record.language, dict(record.case))
