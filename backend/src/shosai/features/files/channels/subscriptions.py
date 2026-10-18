"""Files follows billing: a changed plan marks or clears the person's time over the limits.

A downgrade starts FL-D2's 90 days over storage and FL-D10's over the knowledge limit on
the delivery, not at the next daily pass; a plan that fits again clears the mark. The two
are separate consumers, so each runs in its own transaction and one's failure does not
hold the other. Reminders and removals stay with the daily passes. A workspace's
subscription has no person and is skipped until the workspace quota (FL-D6).
"""

from datetime import timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import transaction_info
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.queues import TaskQueue
from shosai.features.billing.contracts.events import SubscriptionChanged
from shosai.features.files.application.leo_watch import LeoWatch
from shosai.features.files.application.quota_watch import QuotaWatch

DEADLINE: Final = timedelta(seconds=30)


def subscriptions(
    watches: tuple[QuotaWatch, LeoWatch],
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
    )
