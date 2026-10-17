"""Workspaces' tasks: an account event applied to its memberships, and the invariant checks.

A consumer of identity's events queues the account task in the event's delivery
transaction; the task changes each workspace in its own transaction (row-level security
writes a workspace's rows only in its scope), and a home out of reach earns another
delivery. The scheduler runs the inv-14 self-test hourly and the inv-16 seat check daily
in each home (§16.4).
"""

from datetime import datetime, timedelta
from typing import Any, Final

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import (
    MAX_DELIVERIES,
    NO_RETRY,
    RetryPolicy,
    TaskDeclaration,
    TaskHandler,
    TaskKind,
)
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.workspaces.application.account_visibility import (
    AccountEvent,
    apply_account_event,
)
from shosai.features.workspaces.application.invariant_checks import PolicySelfTest, SeatCheck


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


CHECK_POLICY: Final = TaskDeclaration(
    name="workspaces.check_policy",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
CHECK_SEATS: Final = TaskDeclaration(
    name="workspaces.check_seats",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PERIODIC_JOBS: Final = (
    PeriodicJob(CHECK_POLICY, every=timedelta(hours=1)),
    PeriodicJob(CHECK_SEATS, every=timedelta(days=1)),
)


def task_handlers(
    transactions: HomeTransactions, checks: tuple[PolicySelfTest, SeatCheck]
) -> tuple[TaskHandler[Any], ...]:
    """The handlers of workspaces' tasks in this process."""
    policy_check, seat_check = checks

    async def apply(payload: AccountVisibilityPayload) -> None:
        if payload.user_id is None:
            message = "событие аккаунта без аккаунта"
            raise ValueError(message)
        event = AccountEvent(payload.home, payload.user_id, payload.hidden, payload.occurred_at)
        await apply_account_event(transactions, event)

    async def check_policy(payload: HomeTaskPayload) -> None:
        await policy_check.run(payload.home)

    async def check_seats(payload: HomeTaskPayload) -> None:
        await seat_check.run(payload.home)

    return (
        TaskHandler(APPLY_ACCOUNT_EVENT, apply),
        TaskHandler(CHECK_POLICY, check_policy),
        TaskHandler(CHECK_SEATS, check_seats),
    )
