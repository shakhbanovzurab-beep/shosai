"""A thread's history by cursor, newest first (agent plan §3.3, step 4).

History is the person's questions, Leo's answers and the server's notes; tool rounds are the
run's record and are never listed. A page reads the thread's monthly partitions from the
thread's creation on, so older months are pruned, walks the thread's index by moment and
id, and reads only the columns it shows. An answer lists the steps the person saw and the
sources the tools named (step 6), the artifacts the tools handed over by reference (AG-R1),
and the cards it proposed — a server's note the card it tells about — rendered in the person's
language, read with the page in one query (step 9b), and the person's rating of it (step 11a);
a question lists its attachments by name, size and type, never their objects (step 12b).
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from shosai.core.agent_tools.sources import SourceKind
from shosai.core.db.transactions import HomeTransactions
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.domain.attachments import attached_of
from shosai.features.agent.domain.feedback import Rating
from shosai.features.agent.domain.threads import AnswerStatus, HistoryRole
from shosai.features.agent.infrastructure.person_records import AgentFeedbackRecord
from shosai.features.agent.infrastructure.run_records import AgentActionRecord
from shosai.features.agent.infrastructure.thread_records import SPOKEN, AgentMessageRecord
from shosai.features.identity.contracts import Principal

MESSAGE = AgentMessageRecord
ACTION = AgentActionRecord
FEEDBACK = AgentFeedbackRecord
LISTED: Final = tuple(role.value for role in HistoryRole)
NEWEST: Final = Keyset((MESSAGE.created_at.expression, MESSAGE.id.expression), descending=True)
# Только показываемые столбцы: вызовы раунда и дайджесты в страницу не читаются.
SHOWN: Final = load_only(
    MESSAGE.id, MESSAGE.created_at, MESSAGE.role, MESSAGE.text, MESSAGE.status,
    MESSAGE.duration_ms, MESSAGE.steps, MESSAGE.sources, MESSAGE.action_ids, MESSAGE.artifacts,
    MESSAGE.attachments,
)  # fmt: skip


class MessagePosition(BaseModel):
    """Where a page of a thread's messages ended."""

    created_at: datetime
    id: UUID


CODEC: Final = CursorCodec("agent.messages", MessagePosition)


@dataclass(frozen=True, slots=True)
class StepView:
    """A step of an answer: the tool or activity, its detail, how it ended and how long."""

    id: str
    activity: str
    detail: str | None
    status: str
    duration_ms: int | None


def steps_of(stored: list[dict[str, Any]]) -> tuple[StepView, ...]:
    """An answer's steps as its row keeps them."""
    return tuple(
        StepView(
            id=str(step.get("id", "")), activity=str(step.get("activity", "")),
            detail=step.get("detail"), status=str(step.get("status", "")),
            duration_ms=step.get("duration_ms"),
        )
        for step in stored
    )  # fmt: skip


@dataclass(frozen=True, slots=True)
class SourceView:
    """A source of an answer, numbered by its place: what it is, its space, where and what."""

    id: str
    kind: SourceKind
    title: str
    space: str
    locator: str | None
    quote: str


def sources_of(stored: list[dict[str, Any]]) -> tuple[SourceView, ...]:
    """An answer's sources as its row keeps them; one of a kind this build lacks is skipped."""
    kinds = {kind.value for kind in SourceKind}
    return tuple(
        SourceView(
            id=str(source.get("id", "")), kind=SourceKind(source["kind"]),
            title=str(source.get("title", "")), space=str(source.get("space", "")),
            locator=source.get("locator"), quote=str(source.get("quote", "")),
        )
        for source in stored
        if source.get("kind") in kinds
    )  # fmt: skip


@dataclass(frozen=True, slots=True)
class MessageView:
    """A row of the history."""

    id: UUID
    role: HistoryRole
    text: str
    status: AnswerStatus | None
    created_at: datetime
    duration_ms: int | None
    steps: tuple[StepView, ...] = ()
    sources: tuple[SourceView, ...] = ()
    actions: tuple[dict[str, JsonValue], ...] = ()
    artifacts: tuple[dict[str, JsonValue], ...] = ()
    feedback: Rating | None = None
    attachments: tuple[dict[str, Any], ...] = ()


def view_of(record: AgentMessageRecord) -> MessageView:
    """The history's view of a row."""
    status = None if record.status is None else AnswerStatus(record.status)
    return MessageView(
        id=record.id, role=HistoryRole(record.role), text=record.text, status=status,
        created_at=record.created_at, duration_ms=record.duration_ms,
        steps=steps_of(record.steps), sources=sources_of(record.sources),
        artifacts=tuple(record.artifacts),
        attachments=tuple(attached.listed() for attached in attached_of(record.attachments)),
    )  # fmt: skip


async def ratings_of(
    session: AsyncSession, user_id: UUID, rows: list[AgentMessageRecord]
) -> dict[UUID, Rating]:
    """The person's ratings of the page's answers, by message, in one keyed read."""
    answers = [row.id for row in rows if row.role == HistoryRole.ASSISTANT.value]
    if not answers:
        return {}
    found = await session.execute(
        select(FEEDBACK.message_id, FEEDBACK.rating).where(
            FEEDBACK.message_id.in_(answers), FEEDBACK.user_id == user_id
        )
    )
    return {message_id: Rating(rating) for message_id, rating in found.all()}


def position_of(record: AgentMessageRecord) -> MessagePosition:
    """The cursor's position after a row."""
    return MessagePosition(created_at=record.created_at, id=record.id)


class History:
    """The pages of a thread's conversation."""

    def __init__(
        self, transactions: HomeTransactions, threads: Threads, cards: ActionCards
    ) -> None:
        self._transactions = transactions
        self._threads = threads
        self._cards = cards

    async def page(
        self, principal: Principal, thread_id: UUID, request: PageRequest
    ) -> Page[MessageView]:
        """A page of the thread's messages, newest first; `thread_not_found` if hidden."""
        position = None if request.cursor is None else CODEC.decode(request.cursor)
        after = None if position is None else (position.created_at, position.id)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            thread = await self._threads.visible_thread(session, principal.user_id, thread_id)
            statement = (
                select(MESSAGE)
                .options(SHOWN)
                .where(
                    MESSAGE.thread_id == thread.id,
                    MESSAGE.user_id == principal.user_id,
                    MESSAGE.created_at >= thread.created_at,
                    MESSAGE.role.in_(LISTED),
                    SPOKEN,
                )
            )
            rows = list(await session.scalars(NEWEST.page(statement, after, request.limit)))
            cards = await self._cards_of(session, principal, rows[: request.limit])
            ratings = await ratings_of(session, principal.user_id, rows[: request.limit])
        page = page_of(rows, request, CODEC, view_of, position_of)
        items = [
            replace(
                view,
                actions=tuple(cards[i] for i in row.action_ids if i in cards),
                feedback=ratings.get(row.id),
            )
            for view, row in zip(page.items, rows, strict=False)
        ]
        return Page(items=items, next_cursor=page.next_cursor)

    async def _cards_of(
        self, session: AsyncSession, principal: Principal, rows: list[AgentMessageRecord]
    ) -> dict[UUID, dict[str, JsonValue]]:
        """The cards the page's messages name, by id."""
        ids = {action_id for row in rows for action_id in row.action_ids}
        if not ids:
            return {}
        records = list(
            await session.scalars(
                select(ACTION).where(ACTION.id.in_(ids), ACTION.user_id == principal.user_id)
            )
        )
        cards = await self._cards.cards(session, records)
        return {record.id: card for record, card in zip(records, cards, strict=True)}
