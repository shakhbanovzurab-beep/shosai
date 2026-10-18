"""Files follows billing: a changed plan marks or clears the person's time over the limits.

A downgrade starts FL-D2's 90 days over storage and FL-D10's over the knowledge limit on
the delivery, not at the next daily pass; a plan that fits again clears the mark. The two
are separate consumers, so each runs in its own transaction and one's failure does not
hold the other. Reminders and removals stay with the daily passes. A workspace's
subscription has no person and is skipped until the workspace quota (FL-D6).

Files also follows identity's deletion window: a scheduled deletion hides the person's
files from everyone, a cancellation shows them again (ADR 0045 point 6). Both events are
written in the person's scope, so each is applied in its delivery's own transaction.

And files follows workspaces (step 8a): a departed member's workspace files pass to the
owner `member.removed` names, and a deleted workspace's files are erased.
"""

from datetime import timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import transaction_info
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.queues import TaskQueue
from shosai.features.billing.contracts.events import SubscriptionChanged
from shosai.features.files.application.account_window import apply_account_window
from shosai.features.files.application.leo_watch import LeoWatch
from shosai.features.files.application.quota_watch import QuotaWatch
from shosai.features.files.application.workspace_files import (
    erase_workspace_files,
    pass_to_successor,
)
from shosai.features.identity.contracts import AccountDeletionCancelled, AccountDeletionScheduled
from shosai.features.workspaces.contracts.events import MemberRemoved, WorkspaceDeleted

DEADLINE: Final = timedelta(seconds=30)


def subscriptions(
    watches: tuple[QuotaWatch, LeoWatch], outbox: EventOutbox
) -> tuple[EventSubscription[Any], ...]:
    """Files' consumers of other slices' events."""
    watch, leo_watch = watches

    async def follow_plan(
        session: AsyncSession, received: ReceivedEvent[SubscriptionChanged]
    ) -> None:
        user_id = received.event.user_id
        if user_id is None:
            return
        home = transaction_info(session).scope.home
        await watch.apply(session, user_id, await watch.limit(home, user_id))

    async def leo_follows_plan(
        session: AsyncSession, received: ReceivedEvent[SubscriptionChanged]
    ) -> None:
        user_id = received.event.user_id
        if user_id is None:
            return
        home = transaction_info(session).scope.home
        await leo_watch.follow(session, user_id, await leo_watch.limit(home, user_id))

    async def hide_with_account(
        session: AsyncSession, received: ReceivedEvent[AccountDeletionScheduled]
    ) -> None:
        await apply_account_window(
            session, received.event.user_id, hidden=True, occurred_at=received.occurred_at
        )

    async def show_with_account(
        session: AsyncSession, received: ReceivedEvent[AccountDeletionCancelled]
    ) -> None:
        await apply_account_window(
            session, received.event.user_id, hidden=False, occurred_at=received.occurred_at
        )

    return (
        EventSubscription(
            consumer="files.quota_follows_plan",
            event=SubscriptionChanged,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=follow_plan,
        ),
        EventSubscription(
            consumer="files.leo_follows_plan",
            event=SubscriptionChanged,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=leo_follows_plan,
        ),
        EventSubscription(
            consumer="files.hide_with_account",
            event=AccountDeletionScheduled,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=hide_with_account,
        ),
        EventSubscription(
            consumer="files.show_with_account",
            event=AccountDeletionCancelled,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=show_with_account,
        ),
        *workspace_subscriptions(outbox),
    )


def workspace_subscriptions(outbox: EventOutbox) -> tuple[EventSubscription[Any], ...]:
    """Files' consumers of workspaces' events (step 8a)."""

    async def follow_departure(
        session: AsyncSession, received: ReceivedEvent[MemberRemoved]
    ) -> None:
        await pass_to_successor(session, received.event)

    async def erase_with_workspace(
        session: AsyncSession, received: ReceivedEvent[WorkspaceDeleted]
    ) -> None:
        await erase_workspace_files(session, outbox, received.event.org_id)

    return (
        EventSubscription(
            consumer="files.follow_departure",
            event=MemberRemoved,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=follow_departure,
        ),
        EventSubscription(
            consumer="files.erase_with_workspace",
            event=WorkspaceDeleted,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=erase_with_workspace,
        ),
    )
