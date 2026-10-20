"""Notes follows identity's deletion window (MT-D8): scheduled marks it, cancelled clears it.

Identity writes both events in the person's scope, so each delivery's transaction is the
person's and writes their setting row. A redelivered or late event changes nothing.
"""

from datetime import timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.queues import TaskQueue
from shosai.features.identity.contracts import AccountDeletionCancelled, AccountDeletionScheduled
from shosai.features.notes.application.account_window import apply_account_window

DEADLINE: Final = timedelta(seconds=30)


async def hide_with_account(
    session: AsyncSession, received: ReceivedEvent[AccountDeletionScheduled]
) -> None:
    """Mark the person's window."""
    await apply_account_window(
        session, received.event.user_id, hidden=True, occurred_at=received.occurred_at
    )


async def show_with_account(
    session: AsyncSession, received: ReceivedEvent[AccountDeletionCancelled]
) -> None:
    """Clear the person's window."""
    await apply_account_window(
        session, received.event.user_id, hidden=False, occurred_at=received.occurred_at
    )


def subscriptions() -> tuple[EventSubscription[Any], ...]:
    """The slice's consumers, by names that never change."""
    return (
        EventSubscription(
            consumer="notes.hide_with_account",
            event=AccountDeletionScheduled,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=hide_with_account,
        ),
        EventSubscription(
            consumer="notes.show_with_account",
            event=AccountDeletionCancelled,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=show_with_account,
        ),
    )
