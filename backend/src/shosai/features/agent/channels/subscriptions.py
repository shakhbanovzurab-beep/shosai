"""Agent's consumers of workspaces' events (agent plan §3.5 flow 5, step 4), by names that never
change: a departure marks the person's threads of the workspace, a deletion erases them all."""

from datetime import timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.application.departures import Departures, scope_of_departure
from shosai.features.workspaces.contracts.events import MemberRemoved, WorkspaceDeleted

DEADLINE: Final = timedelta(seconds=30)
# Стирание идёт по людям пространства, каждый в своей транзакции.
ERASURE_DEADLINE: Final = timedelta(minutes=2)


def subscriptions(departures: Departures) -> tuple[EventSubscription[Any], ...]:
    """A departed member's threads of the workspace, and a deleted workspace's threads."""

    async def follow(session: AsyncSession, received: ReceivedEvent[MemberRemoved]) -> None:
        await departures.follow(session, received.event, received.occurred_at)

    async def erase_with_workspace(
        session: AsyncSession, received: ReceivedEvent[WorkspaceDeleted]
    ) -> None:
        del session
        await departures.erase_workspace(received.scope.home, received.event.org_id)

    return (
        EventSubscription(
            consumer="agent.follow_departure",
            event=MemberRemoved,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=follow,
            scope=scope_of_departure,
        ),
        EventSubscription(
            consumer="agent.erase_with_workspace",
            event=WorkspaceDeleted,
            queue=TaskQueue.DEFAULT,
            deadline=ERASURE_DEADLINE,
            handle=erase_with_workspace,
        ),
    )
