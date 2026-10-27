"""Meetings' tasks: closing a person's open rooms when their account goes or is frozen (A4c).

Identity's events start it; it finds the rooms with the sweep role and closes each in its own
space, so a repeat after a lost delivery closes nothing more.
"""

from datetime import timedelta
from typing import Final

from shosai.core.tasks.declaration import (
    MAX_DELIVERIES,
    TRANSIENT_FAILURES,
    RetryPolicy,
    TaskDeclaration,
    TaskHandler,
)
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.meetings.application.account_rooms import AccountRooms

CLOSE_ACCOUNT_ROOMS: Final = TaskDeclaration(
    name="meetings.close_account_rooms",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=2),
    retry=RetryPolicy(MAX_DELIVERIES, TRANSIENT_FAILURES),
)


def task_handlers(rooms: AccountRooms) -> tuple[TaskHandler[HomeTaskPayload], ...]:
    """The slice's task handlers in this process."""

    async def close_account_rooms(payload: HomeTaskPayload) -> None:
        if payload.user_id is not None:
            await rooms.close_all(payload.home, payload.user_id)

    return (TaskHandler(CLOSE_ACCOUNT_ROOMS, close_account_rooms),)
