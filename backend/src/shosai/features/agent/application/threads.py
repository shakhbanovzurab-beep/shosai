"""A person's threads with Leo: listed per space, created, renamed and deleted (plan §3.3, step 4).

A workspace's thread is shown while the person is an active member there: every read puts
their active memberships into its statement, so a departed workspace's threads vanish at
once and come back with the membership (AG-D3). A new thread has no title until its first
question names it, and a retried creation answers the thread its key made. Deleting a thread
deletes its messages, ratings and cases with it (foreign keys) and the stored results of its
runs; its runs stay as telemetry and its cards stay in the inbox.
"""

from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import ColumnElement, and_, delete, or_, select
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
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.action_rows import supersede_cards
from shosai.features.agent.domain.threads import (
    ScopeKind,
    ThreadRuleError,
    ThreadScope,
    check_available,
    clean_title,
)
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import (
    AgentThreadRecord,
    AgentToolResultRecord,
)
from shosai.features.identity.contracts import Principal
from shosai.features.workspaces.contracts import MEMBERSHIP_READER

THREAD = AgentThreadRecord
THREAD_CREATES: Final = EffectScope("agent.thread_create", timedelta(hours=24))
NEWEST_ACTIVITY: Final = Keyset(
    (THREAD.last_activity_at.expression, THREAD.id.expression), descending=True
)


class ThreadPosition(BaseModel):
    """Where a page of threads ended."""

    last_activity_at: datetime
    id: UUID


class ThreadCreatePrint(BaseModel):
    """What a creation asked for: a retry with another scope is a reused key."""

    kind: ScopeKind
    org_id: UUID | None


class ThreadMade(BaseModel):
    """The thread a key created."""

    thread_id: UUID


CODEC: Final = CursorCodec("agent.threads", ThreadPosition)


@dataclass(frozen=True, slots=True)
class ThreadView:
    """A thread as the cabinet lists it."""

    id: UUID
    scope: ThreadScope
    title: str | None
    last_activity_at: datetime
    created_at: datetime


def view_of(record: AgentThreadRecord) -> ThreadView:
    """The thread of a row."""
    scope = ThreadScope(ScopeKind(record.scope_kind), record.org_id, record.hub_id)
    return ThreadView(record.id, scope, record.title, record.last_activity_at, record.created_at)


def position_of(record: AgentThreadRecord) -> ThreadPosition:
    """The cursor's position after a row."""
    return ThreadPosition(last_activity_at=record.last_activity_at, id=record.id)


def visible(spaces: Collection[UUID]) -> ColumnElement[bool]:
    """Personal threads, and a workspace's while the person is an active member (AG-D3)."""
    return or_(
        THREAD.scope_kind == ScopeKind.PERSONAL.value,
        and_(THREAD.scope_kind == ScopeKind.WORKSPACE.value, THREAD.org_id.in_(spaces)),
    )


def in_space(scope: ThreadScope) -> tuple[ColumnElement[bool], ...]:
    """Exactly the threads of one space, in the order of the scope index."""
    org = THREAD.org_id.is_(None) if scope.org_id is None else THREAD.org_id == scope.org_id
    return (THREAD.scope_kind == scope.kind.value, org, THREAD.hub_id.is_(None))


def thread_not_found() -> AppError:
    """A thread that is not the person's, or a departed workspace's."""
    return AppError("thread_not_found", HTTPStatus.NOT_FOUND)


def refused(error: ThreadRuleError) -> AppError:
    """A rule of threads as the API's 422."""
    return AppError(error.rule.value, HTTPStatus.UNPROCESSABLE_CONTENT)


class Threads:
    """The person's threads in each of their spaces."""

    def __init__(
        self,
        transactions: HomeTransactions,
        collaborators: tuple[PortDirectory, EffectLedger],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports, self._effects = collaborators
        self._clock = clock

    async def page(
        self, principal: Principal, scope: ThreadScope, request: PageRequest
    ) -> Page[ThreadView]:
        """A page of one space's threads, newest activity first; a departed workspace's none."""
        available(scope)
        position = None if request.cursor is None else CODEC.decode(request.cursor)
        after = None if position is None else (position.last_activity_at, position.id)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            if scope.org_id is not None and scope.org_id not in await self.spaces(
                session, principal.user_id
            ):
                return Page(items=[], next_cursor=None)
            statement = select(THREAD).where(THREAD.user_id == principal.user_id, *in_space(scope))
            rows = list(
                await session.scalars(NEWEST_ACTIVITY.page(statement, after, request.limit))
            )
        return page_of(rows, request, CODEC, view_of, position_of)

    async def create(self, principal: Principal, scope: ThreadScope, client_key: str) -> ThreadView:
        """A new, untitled thread in a space; once per key."""
        available(scope)
        effect = EffectKey(
            THREAD_CREATES,
            account_key(principal.user_id, client_key),
            fingerprint_of(ThreadCreatePrint(kind=scope.kind, org_id=scope.org_id)),
        )
        async with self._transactions.begin(principal.scope()) as session:

            async def write() -> ThreadMade:
                if scope.org_id is not None and scope.org_id not in await self.spaces(
                    session, principal.user_id
                ):
                    raise AppError("workspace_not_found", HTTPStatus.NOT_FOUND)
                now, thread_id = self._clock(), new_id()
                session.add(
                    AgentThreadRecord(
                        id=thread_id, user_id=principal.user_id, scope_kind=scope.kind.value,
                        org_id=scope.org_id, hub_id=None, title=None, last_activity_at=now,
                        created_at=now, updated_at=now,
                    )
                )  # fmt: skip
                await session.flush()
                return ThreadMade(thread_id=thread_id)

            done = await self._effects.once(session, effect, ThreadMade, write)
            return view_of(
                await self.visible_thread(session, principal.user_id, done.outcome.thread_id)
            )

    async def get(self, principal: Principal, thread_id: UUID) -> ThreadView:
        """One of the person's visible threads."""
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            return view_of(await self.visible_thread(session, principal.user_id, thread_id))

    async def rename(self, principal: Principal, thread_id: UUID, title: str) -> ThreadView:
        """The person's own title; Leo never renames it afterwards."""
        try:
            clean = clean_title(title)
        except ThreadRuleError as error:
            raise refused(error) from error
        async with self._transactions.begin(principal.scope()) as session:
            record = await self.visible_thread(session, principal.user_id, thread_id, lock=True)
            record.title, record.title_source, record.updated_at = clean, "person", self._clock()
            await session.flush()
            return view_of(record)

    async def delete(self, principal: Principal, thread_id: UUID) -> None:
        """The thread with its messages, ratings, cases and its runs' stored results."""
        async with self._transactions.begin(principal.scope()) as session:
            record = await self.visible_thread(session, principal.user_id, thread_id, lock=True)
            await erase_threads(session, principal.user_id, (record.id,))

    async def visible_thread(
        self, session: AsyncSession, user_id: UUID, thread_id: UUID, *, lock: bool = False
    ) -> AgentThreadRecord:
        """The person's thread while they may see it; `thread_not_found` otherwise."""
        statement = select(THREAD).where(
            THREAD.id == thread_id,
            THREAD.user_id == user_id,
            visible(await self.spaces(session, user_id)),
        )
        record = await session.scalar(statement.with_for_update() if lock else statement)
        if record is None:
            raise thread_not_found()
        return record

    async def spaces(self, session: AsyncSession, user_id: UUID) -> frozenset[UUID]:
        """The workspaces the person is an active member of now, read in the transaction."""
        memberships = await self._ports.get(MEMBERSHIP_READER).active(session, user_id)
        return frozenset(membership.org_id for membership in memberships)


def available(scope: ThreadScope) -> None:
    """A hub's threads come with hubs (step 20); until then `scope_unavailable`."""
    try:
        check_available(scope.kind)
    except ThreadRuleError as error:
        raise refused(error) from error


async def erase_threads(session: AsyncSession, user_id: UUID, thread_ids: Collection[UUID]) -> int:
    """Delete a person's threads with what goes with them; how many went."""
    if not thread_ids:
        return 0
    await supersede_cards(session, user_id, thread_ids)
    runs = select(AgentRunRecord.id).where(AgentRunRecord.thread_id.in_(thread_ids))
    results = AgentToolResultRecord
    await session.execute(
        delete(results).where(results.user_id == user_id, results.run_id.in_(runs))
    )
    erased = list(
        await session.scalars(
            delete(THREAD)
            .where(THREAD.user_id == user_id, THREAD.id.in_(thread_ids))
            .returning(THREAD.id)
        )
    )
    return len(erased)
