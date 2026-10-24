"""A thread's history by cursor, newest first (agent plan §3.3, step 4).

History is the person's questions, Leo's answers and the server's notes; tool rounds are the
run's record and are never listed. A page reads the thread's monthly partitions from the
thread's creation on, so older months are pruned, walks the thread's index by moment and
id, and reads only the columns it shows. An answer lists the steps the person saw and the
sources the tools named (step 6); its artifacts and cards join it with 9b, its rating with 11
and its attachments with 12: each with the step that writes it.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import load_only

from shosai.core.agent_tools.sources import SourceKind
from shosai.core.db.transactions import HomeTransactions
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.domain.threads import AnswerStatus, HistoryRole
from shosai.features.agent.infrastructure.thread_records import SPOKEN, AgentMessageRecord
from shosai.features.identity.contracts import Principal

MESSAGE = AgentMessageRecord
LISTED: Final = tuple(role.value for role in HistoryRole)
NEWEST: Final = Keyset((MESSAGE.created_at.expression, MESSAGE.id.expression), descending=True)
# Только показываемые столбцы: вызовы раунда и дайджесты в страницу не читаются.
SHOWN: Final = load_only(
    MESSAGE.id, MESSAGE.created_at, MESSAGE.role, MESSAGE.text, MESSAGE.status,
    MESSAGE.duration_ms, MESSAGE.steps, MESSAGE.sources,
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


def view_of(record: AgentMessageRecord) -> MessageView:
    """The history's view of a row."""
    status = None if record.status is None else AnswerStatus(record.status)
    return MessageView(
        id=record.id, role=HistoryRole(record.role), text=record.text, status=status,
        created_at=record.created_at, duration_ms=record.duration_ms,
        steps=steps_of(record.steps), sources=sources_of(record.sources),
    )  # fmt: skip


def position_of(record: AgentMessageRecord) -> MessagePosition:
    """The cursor's position after a row."""
    return MessagePosition(created_at=record.created_at, id=record.id)


class History:
    """The pages of a thread's conversation."""

    def __init__(self, transactions: HomeTransactions, threads: Threads) -> None:
        self._transactions = transactions
        self._threads = threads

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
        return page_of(rows, request, CODEC, view_of, position_of)
