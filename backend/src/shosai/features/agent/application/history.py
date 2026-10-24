"""A thread's history by cursor, newest first (agent plan §3.3, step 4).

History is the person's questions, Leo's answers and the server's notes; tool rounds are the
model's context and are never listed. A page reads the thread's monthly partitions from the
thread's creation on, so older months are pruned, walks the thread's index by moment and
id, and reads only the columns it shows. A message's steps and sources join it with step
6, its artifacts and cards with 9b, its rating with 11 and its attachments with 12: each
with the step that writes it.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import load_only

from shosai.core.db.transactions import HomeTransactions
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.domain.threads import AnswerStatus, HistoryRole
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord
from shosai.features.identity.contracts import Principal

MESSAGE = AgentMessageRecord
LISTED: Final = tuple(role.value for role in HistoryRole)
NEWEST: Final = Keyset((MESSAGE.created_at.expression, MESSAGE.id.expression), descending=True)
# Только показываемые столбцы: шаги, источники и вызовы раунда в страницу не читаются.
SHOWN: Final = load_only(
    MESSAGE.id, MESSAGE.created_at, MESSAGE.role, MESSAGE.text, MESSAGE.status,
    MESSAGE.duration_ms,
)  # fmt: skip


class MessagePosition(BaseModel):
    """Where a page of a thread's messages ended."""

    created_at: datetime
    id: UUID


CODEC: Final = CursorCodec("agent.messages", MessagePosition)


@dataclass(frozen=True, slots=True)
class MessageView:
    """A row of the history."""

    id: UUID
    role: HistoryRole
    text: str
    status: AnswerStatus | None
    created_at: datetime
    duration_ms: int | None


def view_of(record: AgentMessageRecord) -> MessageView:
    """The history's view of a row."""
    status = None if record.status is None else AnswerStatus(record.status)
    return MessageView(
        id=record.id, role=HistoryRole(record.role), text=record.text, status=status,
        created_at=record.created_at, duration_ms=record.duration_ms,
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
                )
            )
            rows = list(await session.scalars(NEWEST.page(statement, after, request.limit)))
        return page_of(rows, request, CODEC, view_of, position_of)
