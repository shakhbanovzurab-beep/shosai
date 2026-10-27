"""The person's own changes to what Leo remembers (memory step 3, Leo §7.2 "User controls").

Editing a statement never rewrites it: the old fact closes and its successor — the person's
own words, confirmed — takes its place, and a retry with the same `Idempotency-Key` answers
the first successor instead of failing on the closed fact. Editing a candidate accepts it.
Accepting a candidate that proposes to replace a current fact closes that fact. Forgetting and
turning down are idempotent. Forgetting everything ends every fact and candidate at once and
empties the summary. Nothing here calls a model: a new statement's vector comes from the
embedding pass (step 4), and until then it is listed but not recalled.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import Update, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import (
    EffectKey,
    EffectLedger,
    EffectScope,
    account_key,
    fingerprint_of,
)
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.features.identity.contracts import Principal
from shosai.features.memory.application.fact_list import FactLists, FactView, view_of
from shosai.features.memory.application.fact_rows import (
    FACT,
    fact_of,
    successor_row,
    visible,
    write_back,
)
from shosai.features.memory.domain.facts import (
    EndReason,
    Fact,
    FactStatus,
    MemoryRuleError,
    MemorySource,
    accept,
    clean_statement,
    forget,
    pin,
    supersede,
)
from shosai.features.memory.infrastructure.presence import TTL_SECONDS, has_memories_key
from shosai.features.memory.infrastructure.records import MemoryFactRecord, MemorySummaryRecord

# Ключ клиента живёт сутки: повтор правки позже — уже новая правка.
EDITS: Final = EffectScope("memory.fact_edits", keep=timedelta(days=1))
NOT_FOUND: Final = "memory_fact_not_found"


class EditPrint(BaseModel):
    """What a statement edit asked for, to tell a retry from a reused key."""

    fact_id: UUID
    statement: str
    pinned: bool | None


class Edited(BaseModel):
    """The fact an edit left current."""

    fact_id: UUID


def not_found() -> AppError:
    """The one answer for a fact the person cannot change: gone, another's, or never there."""
    return AppError(NOT_FOUND, HTTPStatus.NOT_FOUND)


def invalid(error: MemoryRuleError) -> AppError:
    """A rule of facts as the API's error."""
    return AppError(error.rule.value, HTTPStatus.UNPROCESSABLE_CONTENT)


class FactChanges:
    """Edit, pin, accept, forget and forget everything, as the person."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[FactLists, EffectLedger, Redis],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._lists, self._effects, self._valkey = collaborators
        self._clock = clock

    async def _row(
        self, session: AsyncSession, principal: Principal, fact_id: UUID
    ) -> MemoryFactRecord:
        spaces = await self._lists.spaces(session, principal.user_id)
        row = await session.scalar(
            select(FACT)
            .where(FACT.id == fact_id, visible(principal.user_id, spaces))
            .with_for_update()
        )
        if row is None:
            raise not_found()
        return row

    async def _view(
        self, session: AsyncSession, principal: Principal, row: MemoryFactRecord
    ) -> FactView:
        titles = await self._lists.titles(session, principal.user_id, [row])
        return view_of(row, titles.get)

    async def edit(
        self,
        principal: Principal,
        fact_id: UUID,
        change: tuple[str | None, bool | None],
        client_key: str,
    ) -> FactView:
        """A new statement supersedes the fact, once per key; a pin changes only the pin."""
        statement, pinned = change
        if statement is None:
            return await self._pin(principal, fact_id, pinned=pinned)
        try:
            clean = clean_statement(statement)
        except MemoryRuleError as error:
            raise invalid(error) from None
        effect = EffectKey(
            EDITS,
            account_key(principal.user_id, client_key),
            fingerprint_of(EditPrint(fact_id=fact_id, statement=clean, pinned=pinned)),
        )
        async with self._transactions.begin(principal.scope()) as session:

            async def write() -> Edited:
                row = await self._row(session, principal, fact_id)
                return Edited(fact_id=await self._supersede(session, row, clean, pinned=pinned))

            done = await self._effects.once(session, effect, Edited, write)
            row = await session.get(FACT, done.outcome.fact_id)
            if row is None:
                raise not_found()
            await self._mark_present(principal.user_id)
            return await self._view(session, principal, row)

    async def _supersede(
        self, session: AsyncSession, row: MemoryFactRecord, statement: str, *, pinned: bool | None
    ) -> UUID:
        now, old = self._clock(), fact_of(row)
        if statement == old.statement and old.current:
            if pinned is not None:
                write_back(row, pin(old, pinned=pinned, now=now), now)
            return row.id
        successor = Fact(
            id=new_id(), kind=old.kind, statement=statement, status=FactStatus.ACTIVE,
            source=MemorySource.USER_EDIT, created_at=now, last_confirmed_at=now, explicit=True,
            confirmed=True, confirmations=old.confirmations + 1,
        )  # fmt: skip
        if old.pending:
            await self._replace_proposed(session, row, now)
        closed, opened = supersede(old, successor, now)
        if pinned is not None:
            opened = pin(opened, pinned=pinned, now=now)
        write_back(row, closed, now)
        session.add(successor_row(row, opened, now))
        await session.flush()
        return opened.id

    async def _pin(self, principal: Principal, fact_id: UUID, *, pinned: bool | None) -> FactView:
        async with self._transactions.begin(principal.scope()) as session:
            row = await self._row(session, principal, fact_id)
            if pinned is not None:
                try:
                    write_back(
                        row, pin(fact_of(row), pinned=pinned, now=self._clock()), self._clock()
                    )
                except MemoryRuleError as error:
                    raise invalid(error) from None
            return await self._view(session, principal, row)

    async def accept(self, principal: Principal, fact_id: UUID) -> FactView:
        """Remember: the candidate becomes the person's fact; a repeat changes nothing."""
        async with self._transactions.begin(principal.scope()) as session:
            row = await self._row(session, principal, fact_id)
            fact = fact_of(row)
            if fact.pending:
                now = self._clock()
                await self._replace_proposed(session, row, now)
                write_back(row, accept(fact, now), now)
            view = await self._view(session, principal, row)
        await self._mark_present(principal.user_id)
        return view

    async def _replace_proposed(
        self, session: AsyncSession, row: MemoryFactRecord, now: datetime
    ) -> None:
        """The current fact a candidate proposed to replace closes in its favour."""
        if row.replaces is None:
            return
        old = await session.scalar(
            select(FACT)
            .where(FACT.id == row.replaces, FACT.user_id == row.user_id)
            .with_for_update()
        )
        if old is not None and fact_of(old).current:
            old.valid_to, old.superseded_by, old.pinned, old.updated_at = now, row.id, False, now

    async def forget(self, principal: Principal, fact_id: UUID) -> None:
        """Forget a fact or turn a candidate down; forgetting it again answers the same."""
        async with self._transactions.begin(principal.scope()) as session:
            row = await session.scalar(
                select(FACT)
                .where(FACT.id == fact_id, FACT.user_id == principal.user_id)
                .with_for_update()
            )
            if row is not None and row.status == FactStatus.FORGOTTEN.value:
                return
            row = await self._row(session, principal, fact_id)
            now = self._clock()
            write_back(row, forget(fact_of(row), EndReason.FORGOT, now), now)

    async def forget_all(self, principal: Principal) -> None:
        """Every fact and candidate ends at once, and the summary is emptied."""
        now = self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            await session.execute(self._end(principal.user_id, EndReason.FORGOT_ALL, now))
            await session.execute(
                delete(MemorySummaryRecord).where(MemorySummaryRecord.user_id == principal.user_id)
            )
        await self._valkey.delete(has_memories_key(principal.user_id))

    async def turn_down_imported(self, principal: Principal) -> None:
        """Every carried-over candidate is turned down at once (MM-D8)."""
        now = self._clock()
        async with self._transactions.begin(principal.scope()) as session:
            await session.execute(
                self._end(principal.user_id, EndReason.TURNED_DOWN, now)
                .where(FACT.status == FactStatus.CANDIDATE.value)
                .where(FACT.source_kind == MemorySource.IMPORTED.value)
            )

    @staticmethod
    def _end(user_id: UUID, reason: EndReason, now: datetime) -> Update:
        return (
            update(FACT)
            .where(
                FACT.user_id == user_id,
                FACT.status.in_((FactStatus.ACTIVE.value, FactStatus.CANDIDATE.value)),
                FACT.valid_to.is_(None),
            )
            .values(status=FactStatus.FORGOTTEN.value, pinned=False, ended_reason=reason.value,
                    ended_at=now, updated_at=now)
        )  # fmt: skip

    async def _mark_present(self, user_id: UUID) -> None:
        await self._valkey.set(has_memories_key(user_id), "1", ex=TTL_SECONDS)
