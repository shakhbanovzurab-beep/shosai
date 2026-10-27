"""What Leo remembers, page by page, with the counts the settings row shows (memory step 3).

Waiting candidates come first, then current facts, newest first within each; the server
filters by status, kind, source, conversation and words, so search and the kind filter cover
every page, not only the loaded ones. The draft's carried-over candidates are listed only in
their own list (MM-D8). A meeting's fact names the meeting as it is titled now, read through
notes as the person; a meeting the person can no longer read is named by nobody.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import ColumnElement, and_, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.memory.application.fact_rows import FACT, visible
from shosai.features.memory.domain.facts import FactKind, FactStatus, MemorySource
from shosai.features.memory.infrastructure.records import MemoryFactRecord
from shosai.features.notes.contracts import MEETING_READER
from shosai.features.workspaces.contracts import MEMBERSHIP_READER, Viewer

# Кандидаты раньше фактов: 'candidate' > 'active', и весь ключ — по убыванию (индекс listing).
LISTING: Final = Keyset(
    (FACT.status.expression, FACT.created_at.expression, FACT.id.expression), descending=True
)
IMPORTED_CANDIDATE: Final = and_(
    FACT.status == FactStatus.CANDIDATE.value, FACT.source_kind == MemorySource.IMPORTED.value
)
LIKE_SPECIALS: Final = str.maketrans({"\\": "\\\\", "%": "\\%", "_": "\\_"})


class FactPosition(BaseModel):
    """Where a page of facts ended."""

    status: str
    created_at: datetime
    id: UUID


CODEC: Final = CursorCodec("memory.facts", FactPosition)


@dataclass(frozen=True, slots=True)
class FactQuery:
    """Which facts a page lists."""

    status: FactStatus | None = None
    kind: FactKind | None = None
    imported: bool = False
    thread_id: UUID | None = None
    words: str | None = None


@dataclass(frozen=True, slots=True)
class FactView:
    """A fact as the cabinet shows it."""

    id: UUID
    kind: FactKind
    statement: str
    status: FactStatus
    pinned: bool
    source: MemorySource
    title: str | None
    thread_id: UUID | None
    message_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Counts:
    """How many facts, waiting candidates and carried-over candidates the person has."""

    active: int
    candidates: int
    imported: int


def _ref(row: MemoryFactRecord, name: str) -> UUID | None:
    value = row.source_ref.get(name)
    return UUID(value) if value else None


def view_of(row: MemoryFactRecord, titles: Callable[[UUID], str | None]) -> FactView:
    """The cabinet's view of a row, its meeting named by `titles`."""
    meeting = _ref(row, "meeting_id")
    return FactView(
        id=row.id,
        kind=FactKind(row.kind),
        statement=row.statement,
        status=FactStatus(row.status),
        pinned=row.pinned,
        source=MemorySource(row.source_kind),
        title=titles(meeting) if meeting else None,
        thread_id=row.thread_id,
        message_id=_ref(row, "message_id"),
        created_at=row.created_at,
    )


def filters(query: FactQuery) -> list[ColumnElement[bool]]:
    """The query's conditions beyond what the person may see."""
    conditions: list[ColumnElement[bool]] = [
        IMPORTED_CANDIDATE if query.imported else not_(IMPORTED_CANDIDATE)
    ]
    if query.status is not None:
        conditions.append(FACT.status == query.status.value)
    if query.kind is not None:
        conditions.append(FACT.kind == query.kind.value)
    if query.thread_id is not None:
        conditions.append(FACT.thread_id == query.thread_id)
    if query.words:
        pattern = f"%{query.words.translate(LIKE_SPECIALS)}%"
        conditions.append(FACT.statement.ilike(pattern, escape="\\"))
    return conditions


class FactLists:
    """Pages of the person's facts and their counts."""

    def __init__(self, transactions: HomeTransactions, ports: PortDirectory) -> None:
        self._transactions = transactions
        self._ports = ports

    async def spaces(self, session: AsyncSession, user_id: UUID) -> frozenset[UUID]:
        """The workspaces the person is a member of now."""
        memberships = await self._ports.get(MEMBERSHIP_READER).active(session, user_id)
        return frozenset(membership.org_id for membership in memberships)

    async def page(
        self, principal: Principal, query: FactQuery, request: PageRequest
    ) -> tuple[Page[FactView], Counts]:
        """One page of the query's facts and the person's counts, read together."""
        position = None if request.cursor is None else CODEC.decode(request.cursor)
        after = None if position is None else (position.status, position.created_at, position.id)
        user_id = principal.user_id
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            seen = visible(user_id, await self.spaces(session, user_id))
            statement = select(FACT).where(seen, *filters(query))
            rows = list(await session.scalars(LISTING.page(statement, after, request.limit)))
            counts = await self.counts(session, seen)
            titles = await self.titles(session, user_id, rows)
        page = page_of(rows, request, CODEC, lambda row: view_of(row, titles.get), _position)
        return page, counts

    async def counts(self, session: AsyncSession, seen: ColumnElement[bool]) -> Counts:
        """The settings row's counts, in one statement."""
        active = FACT.status == FactStatus.ACTIVE.value
        waiting = and_(FACT.status == FactStatus.CANDIDATE.value, not_(IMPORTED_CANDIDATE))
        row = (
            await session.execute(
                select(
                    func.count().filter(active),
                    func.count().filter(waiting),
                    func.count().filter(IMPORTED_CANDIDATE),
                ).where(seen)
            )
        ).one()
        return Counts(active=row[0], candidates=row[1], imported=row[2])

    async def titles(
        self, session: AsyncSession, user_id: UUID, rows: Sequence[MemoryFactRecord]
    ) -> dict[UUID, str]:
        """The titles of the meetings the rows came from, as the person may read them."""
        meetings = {ref for row in rows if (ref := _ref(row, "meeting_id")) is not None}
        if not meetings:
            return {}
        found = await self._ports.get(MEETING_READER).facts(session, Viewer(user_id), meetings)
        return {meeting_id: facts.title for meeting_id, facts in found.items()}


def _position(row: MemoryFactRecord) -> FactPosition:
    return FactPosition(status=row.status, created_at=row.created_at, id=row.id)
