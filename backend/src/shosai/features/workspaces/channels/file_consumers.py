"""Workspaces follows files: a deleted file leaves every workspace it was shared in (§3.6).

The owner's deletion, and the removal after FL-D2's 90 days, write `files.file.deleted` in
the owner's scope, so the delivery's transaction sees the owner's active workspaces, where
every item of the file lives. Support's restore brings a file back shared nowhere, so
nothing follows it. A redelivered event finds nothing left to withdraw.
"""

from datetime import timedelta
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.queues import TaskQueue
from shosai.features.files.contracts.events import FileDeleted
from shosai.features.workspaces.application.file_items import locked_items, withdraw_items

DEADLINE: Final = timedelta(seconds=30)


class DeletedFiles:
    """Withdraws a deleted file's knowledge items with their grants."""

    def __init__(self, outbox: EventOutbox) -> None:
        self._outbox = outbox

    async def withdraw(self, session: AsyncSession, received: ReceivedEvent[FileDeleted]) -> None:
        """Take a person's deleted file out of every workspace it was shared in."""
        event = received.event
        # Элементы файла пространства — его собственные: они уходят вместе с ним.
        if event.user_id is None or event.org_id is not None:
            return
        items = await locked_items(session, event.file_id, event.user_id)
        await withdraw_items(session, self._outbox, items)

    def subscriptions(self) -> tuple[EventSubscription[FileDeleted]]:
        """The consumer, by a name that never changes."""
        return (
            EventSubscription(
                "workspaces.withdraw_deleted_file",
                FileDeleted,
                TaskQueue.DEFAULT,
                DEADLINE,
                self.withdraw,
            ),
        )
