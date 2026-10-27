"""Memory's consumers of departures, by names that never change (memory step 8, MM-D4).

A workspace's departure marks the person's facts of it, as the departed person; its deletion
erases them all; a meeting's deletion marks its facts for the day notes purges it, and its
restore settles them at once.
"""

from datetime import timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.queues import TaskQueue
from shosai.features.memory.application.departures import Departures
from shosai.features.notes.contracts.events import MeetingDeleted, MeetingRestored
from shosai.features.workspaces.contracts.events import MemberRemoved, WorkspaceDeleted

DEADLINE: Final = timedelta(seconds=30)
# Стирание и отметки идут по людям, каждый в своей транзакции.
SWEEP_DEADLINE: Final = timedelta(minutes=2)


def departed(event: MemberRemoved, scope: TenancyScope) -> TenancyScope:
    """The departed person in the event's home: their facts are theirs to mark."""
    return TenancyScope(scope.home, event.user_id)


def departure_subscriptions(departures: Departures) -> tuple[EventSubscription[Any], ...]:
    """The facts that follow their sources."""

    async def left(session: AsyncSession, received: ReceivedEvent[MemberRemoved]) -> None:
        event = received.event
        await departures.left(session, event.user_id, event.org_id, received.occurred_at)

    async def workspace_gone(
        session: AsyncSession, received: ReceivedEvent[WorkspaceDeleted]
    ) -> None:
        del session
        await departures.workspace_deleted(received.scope.home, received.event.org_id)

    async def meeting_gone(session: AsyncSession, received: ReceivedEvent[MeetingDeleted]) -> None:
        del session
        await departures.meeting_deleted(
            received.scope.home, received.event.meeting_id, received.occurred_at
        )

    async def meeting_back(session: AsyncSession, received: ReceivedEvent[MeetingRestored]) -> None:
        del session
        await departures.meeting_restored(received.scope.home, received.event.meeting_id)

    return (
        EventSubscription(
            consumer="memory.follow_departure", event=MemberRemoved, queue=TaskQueue.DEFAULT,
            deadline=DEADLINE, handle=left, scope=departed,
        ),
        EventSubscription(
            consumer="memory.erase_with_workspace", event=WorkspaceDeleted,
            queue=TaskQueue.DEFAULT, deadline=SWEEP_DEADLINE, handle=workspace_gone,
        ),
        EventSubscription(
            consumer="memory.hide_with_meeting", event=MeetingDeleted, queue=TaskQueue.DEFAULT,
            deadline=SWEEP_DEADLINE, handle=meeting_gone,
        ),
        EventSubscription(
            consumer="memory.return_with_meeting", event=MeetingRestored,
            queue=TaskQueue.DEFAULT, deadline=SWEEP_DEADLINE, handle=meeting_back,
        ),
    )  # fmt: skip
