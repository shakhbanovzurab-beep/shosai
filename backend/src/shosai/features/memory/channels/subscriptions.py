"""Memory's consumers of events, by names that never change: a completed turn sends its
admission off the turn's path (memory step 5)."""

from datetime import timedelta
from typing import Any, Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.memory.channels.tasks import ADMIT_TURN, TurnTask

DEADLINE: Final = timedelta(seconds=30)


class TurnQueue(Protocol):
    """Sends a turn's admission to its queue."""

    async def send(self, task: TaskDeclaration[TurnTask], payload: TurnTask) -> str:
        """Queue the task; its id."""
        ...


def subscriptions(queue: TurnQueue) -> tuple[EventSubscription[Any], ...]:
    """A completed turn's admission."""

    async def admit_turn(session: AsyncSession, received: ReceivedEvent[TurnCompleted]) -> None:
        del session
        event = received.event
        await queue.send(
            ADMIT_TURN, turn_task(received.scope.home.value, event.user_id, event.run_id)
        )

    return (
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
