"""Workspaces' consumers of identity's events: an account's deletion window (ADR 0053 point 4).

A scheduled deletion hides the account's memberships, a cancelled one shows them again.
The handler only queues the task in the delivery's transaction; the delivery mark written
there makes a redelivered event queue nothing more.
"""

from datetime import timedelta
from typing import Final, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.payloads import TaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.identity.contracts import AccountDeletionCancelled, AccountDeletionScheduled
from shosai.features.workspaces.channels.tasks import (
    APPLY_ACCOUNT_EVENT,
    AccountVisibilityPayload,
)

DEADLINE: Final = timedelta(seconds=30)


class TaskQueueing(Protocol):
    """Queues a task; the process's `TaskSender`."""

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Queue one run of the task; return its task id."""
        ...


class AccountWindow:
    """Turns identity's deletion window into hidden and restored memberships."""

    def __init__(self, tasks: TaskQueueing) -> None:
        self._tasks = tasks

    async def scheduled(
        self, _session: AsyncSession, received: ReceivedEvent[AccountDeletionScheduled]
    ) -> None:
        """Hide the account's memberships."""
        await self._queue(received, hidden=True)

    async def cancelled(
        self, _session: AsyncSession, received: ReceivedEvent[AccountDeletionCancelled]
    ) -> None:
        """Show the account's memberships again."""
        await self._queue(received, hidden=False)

    async def _queue(
        self,
        received: ReceivedEvent[AccountDeletionScheduled] | ReceivedEvent[AccountDeletionCancelled],
        *,
        hidden: bool,
    ) -> None:
        payload = AccountVisibilityPayload(
            home=received.scope.home,
            user_id=received.event.user_id,
            hidden=hidden,
            occurred_at=received.occurred_at,
        )
        await self._tasks.send(APPLY_ACCOUNT_EVENT, payload)

    def subscriptions(
        self,
    ) -> tuple[
        EventSubscription[AccountDeletionScheduled], EventSubscription[AccountDeletionCancelled]
    ]:
        """The two consumers, by names that never change."""
        return (
            EventSubscription(
                "workspaces.hide_memberships",
                AccountDeletionScheduled,
                TaskQueue.DEFAULT,
                DEADLINE,
                self.scheduled,
            ),
            EventSubscription(
                "workspaces.restore_memberships",
                AccountDeletionCancelled,
                TaskQueue.DEFAULT,
                DEADLINE,
                self.cancelled,
            ),
        )
