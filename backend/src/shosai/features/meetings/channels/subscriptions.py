"""Meetings follows identity: a scheduled deletion or a block closes the person's rooms (A4c).

Each event queues the closing task for the person's home; the task does the work outside the
delivery's transaction, and a redelivered event queues a task that closes nothing more.
"""

from datetime import timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.core.tasks.sender import TaskSender
from shosai.features.identity.contracts import AccountBlocked, AccountDeletionScheduled
from shosai.features.meetings.channels.tasks import CLOSE_ACCOUNT_ROOMS

DEADLINE: Final = timedelta(seconds=30)


def subscriptions(tasks: TaskSender) -> tuple[EventSubscription[Any], ...]:
    """The slice's consumers, by names that never change."""

    async def close_for_deletion(
        session: AsyncSession, received: ReceivedEvent[AccountDeletionScheduled]
    ) -> None:
        del session
        payload = HomeTaskPayload(home=received.scope.home, user_id=received.event.user_id)
        await tasks.send(CLOSE_ACCOUNT_ROOMS, payload)

    async def close_for_block(
        session: AsyncSession, received: ReceivedEvent[AccountBlocked]
    ) -> None:
        del session
        payload = HomeTaskPayload(home=received.scope.home, user_id=received.event.user_id)
        await tasks.send(CLOSE_ACCOUNT_ROOMS, payload)

    return (
        EventSubscription(
            consumer="meetings.close_rooms_for_deletion",
            event=AccountDeletionScheduled,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=close_for_deletion,
        ),
        EventSubscription(
            consumer="meetings.close_rooms_for_block",
            event=AccountBlocked,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=close_for_block,
        ),
    )
