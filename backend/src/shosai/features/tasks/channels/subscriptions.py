"""Tasks' consumers of workspaces' events (tasks plan step 6), by names that never change."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.ports.directory import PortDirectory
from shosai.core.tasks.queues import TaskQueue
from shosai.features.tasks.application.workspace_lifecycle import (
    clear_project,
    follow_departure,
    scope_of_departure,
    scope_of_workspace,
)
from shosai.features.workspaces.contracts.events import MemberRemoved, ProjectDeleted

DEADLINE: Final = timedelta(seconds=30)


def subscriptions(
    ports: PortDirectory, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> tuple[EventSubscription[Any], ...]:
    """A departed member's tasks and a deleted project's."""

    async def follow(session: AsyncSession, received: ReceivedEvent[MemberRemoved]) -> None:
        await follow_departure(session, ports, received.event, clock())

    async def forget_project(
        session: AsyncSession, received: ReceivedEvent[ProjectDeleted]
    ) -> None:
        await clear_project(session, received.event, clock())

    return (
        EventSubscription(
            consumer="tasks.follow_departure",
            event=MemberRemoved,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=follow,
            scope=scope_of_departure,
        ),
        EventSubscription(
            consumer="tasks.forget_project",
            event=ProjectDeleted,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=forget_project,
            scope=scope_of_workspace,
        ),
    )
