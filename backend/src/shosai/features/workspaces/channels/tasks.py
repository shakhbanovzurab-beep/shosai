"""Workspaces' tasks: applying an account event to the account's memberships.

A consumer of identity's events queues the task in the event's delivery transaction; the
task changes each workspace in its own transaction (row-level security writes a
workspace's rows only in its scope). A home out of reach earns another delivery.
"""

from datetime import datetime, timedelta
from typing import Final

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.tasks.declaration import MAX_DELIVERIES, RetryPolicy, TaskDeclaration, TaskHandler
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.workspaces.application.account_visibility import (
    AccountEvent,
    apply_account_event,
)


class AccountVisibilityPayload(HomeTaskPayload):
    """An account whose memberships are hidden or shown again, and when that happened."""

    hidden: bool
    occurred_at: datetime


APPLY_ACCOUNT_EVENT: Final = TaskDeclaration(
    name="workspaces.apply_account_event",
    queue=TaskQueue.DEFAULT,
    payload=AccountVisibilityPayload,
    deadline=timedelta(seconds=60),
    retry=RetryPolicy(max_deliveries=MAX_DELIVERIES, retry_on=(HomeUnavailableError,)),
)


def task_handlers(transactions: HomeTransactions) -> tuple[TaskHandler[AccountVisibilityPayload]]:
    """The handlers of workspaces' tasks in this process."""

    async def apply(payload: AccountVisibilityPayload) -> None:
        if payload.user_id is None:
            message = "событие аккаунта без аккаунта"
            raise ValueError(message)
        event = AccountEvent(payload.home, payload.user_id, payload.hidden, payload.occurred_at)
        await apply_account_event(transactions, event)

    return (TaskHandler(APPLY_ACCOUNT_EVENT, apply),)
