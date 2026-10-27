"""Memory's consumers of events, by names that never change: a completed turn sends its
admission off the turn's path (memory step 5), and a meeting's first notes its recollection
(step 9, MM-D5); a rewrite of the notes recollects nothing again."""

from datetime import timedelta
from typing import Any, Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.payloads import TaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.memory.channels.tasks import ADMIT_TURN, RECOLLECT, MeetingTask, TurnTask
from shosai.features.notes.contracts.events import NotesReady

DEADLINE: Final = timedelta(seconds=30)
FIRST_NOTES: Final = 1


class TurnQueue(Protocol):
    """Sends memory's tasks to their queue."""

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Queue the task; its id."""
        ...


def subscriptions(queue: TurnQueue) -> tuple[EventSubscription[Any], ...]:
    """A completed turn's admission and a meeting's recollection."""

    async def admit_turn(session: AsyncSession, received: ReceivedEvent[TurnCompleted]) -> None:
        del session
        event = received.event
        await queue.send(
            ADMIT_TURN, turn_task(received.scope.home.value, event.user_id, event.run_id)
        )

    async def recollect(session: AsyncSession, received: ReceivedEvent[NotesReady]) -> None:
        del session
        event = received.event
        if event.revision != FIRST_NOTES or event.user_id is None:
            return
        task = MeetingTask(
            home=received.scope.home, user_id=event.user_id, meeting_id=event.meeting_id
        )
        await queue.send(RECOLLECT, task)

    return (
        EventSubscription(
            consumer="memory.recollect_meeting",
            event=NotesReady,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=recollect,
        ),
        EventSubscription(
            consumer="memory.admit_turn",
            event=TurnCompleted,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=admit_turn,
        ),
    )


def turn_task(home: str, user_id: UUID, run_id: UUID) -> TurnTask:
    """The admission task of one turn."""
    return TurnTask.model_validate({"home": home, "user_id": user_id, "run_id": run_id})
