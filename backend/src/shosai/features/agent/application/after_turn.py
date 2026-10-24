"""What follows a turn, off its path (Leo §5.2 step 12; agent plan §3.5 flow 1, step 5b).

`agent.turn.completed` — the turn's own event, delivered after its final transaction — sends
the tasks that are due: the thread's title by the utility model after its first answer, while
the person has not renamed it, and the folding of its oldest turns into the summary once the
recent segment passes 70 % of its cap. Both are best effort and safe to repeat: a title stays
the question's words, and while compaction lags the context builder drops the oldest turns.
"""

from datetime import timedelta
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.homes import Home
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.domain.budgets import needs_compaction
from shosai.features.agent.domain.threads import AnswerStatus, MessageRole
from shosai.features.agent.infrastructure.thread_records import (
    SPOKEN,
    AgentMessageRecord,
    AgentThreadRecord,
)

MESSAGE = AgentMessageRecord
QUESTION_TITLE: Final = "question"


class ThreadTask(HomeTaskPayload):
    """Work on one of a person's threads."""

    thread_id: UUID


TITLE_THREAD: Final = TaskDeclaration(
    name="agent.title_thread",
    queue=TaskQueue.DEFAULT,
    payload=ThreadTask,
    deadline=timedelta(seconds=60),
    retry=NO_RETRY,
)
COMPACT_THREAD: Final = TaskDeclaration(
    name="agent.compact_thread",
    queue=TaskQueue.DEFAULT,
    payload=ThreadTask,
    deadline=timedelta(minutes=2),
    retry=NO_RETRY,
)


class ThreadQueue(Protocol):
    """Sends a thread's work to the default queue."""

    async def send(self, task: TaskDeclaration[ThreadTask], payload: ThreadTask) -> str:
        """Queue the task; its id."""
        ...


class AfterTurn:
    """Decides what a completed turn's thread needs next."""

    def __init__(self, queue: ThreadQueue) -> None:
        self._queue = queue

    async def follow(self, session: AsyncSession, completed: TurnCompleted, home: Home) -> None:
        """Send the title and the compaction when they are due."""
        thread = await session.get(AgentThreadRecord, completed.thread_id)
        if thread is None:
            return
        work = ThreadTask(home=home, user_id=completed.user_id, thread_id=thread.id)
        if thread.title_source == QUESTION_TITLE and await answers(session, thread) == 1:
            await self._queue.send(TITLE_THREAD, work)
        if needs_compaction(await recent_tokens(session, thread)):
            await self._queue.send(COMPACT_THREAD, work)


async def answers(session: AsyncSession, thread: AgentThreadRecord) -> int:
    """How many answers the thread holds, counting up to two."""
    found = await session.scalars(
        select(MESSAGE.id)
        .where(
            MESSAGE.thread_id == thread.id,
            MESSAGE.created_at >= thread.created_at,
            MESSAGE.role == MessageRole.ASSISTANT.value,
            SPOKEN,
        )
        .limit(2)
    )
    return len(list(found))


async def recent_tokens(session: AsyncSession, thread: AgentThreadRecord) -> int:
    """The estimated tokens of the messages the summary has not folded yet."""
    since = thread.created_at
    if thread.summary_upto is not None:
        folded = await session.scalar(
            select(MESSAGE.created_at).where(
                MESSAGE.id == thread.summary_upto, MESSAGE.thread_id == thread.id
            )
        )
        since = folded or since
    conditions = [
        MESSAGE.thread_id == thread.id,
        MESSAGE.created_at >= since,
        MESSAGE.role.in_((MessageRole.USER.value, MessageRole.ASSISTANT.value)),
        or_(MESSAGE.status.is_(None), MESSAGE.status != AnswerStatus.FAILED.value),
        SPOKEN,
    ]
    if thread.summary_upto is not None:
        conditions.append(MESSAGE.id != thread.summary_upto)
    total = await session.scalar(
        select(func.coalesce(func.sum(MESSAGE.tokens), 0)).where(*conditions)
    )
    return int(total or 0)
