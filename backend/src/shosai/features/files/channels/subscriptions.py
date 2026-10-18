"""Files follows billing: a changed plan marks or clears the person's time over the limit.

A downgrade starts FL-D2's 90 days on the delivery, not at the next daily pass; a plan that
fits again clears the mark. Reminders and removal stay with the daily pass. A workspace's
subscription has no person and is skipped until the workspace quota (FL-D6).
"""

from datetime import timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import transaction_info
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.queues import TaskQueue
from shosai.features.billing.contracts.events import SubscriptionChanged
from shosai.features.files.application.quota_watch import QuotaWatch

DEADLINE: Final = timedelta(seconds=30)


def subscriptions(watch: QuotaWatch) -> tuple[EventSubscription[Any], ...]:
    """Files' consumers of other slices' events."""

    async def follow_plan(
        session: AsyncSession, received: ReceivedEvent[SubscriptionChanged]
    ) -> None:
        user_id = received.event.user_id
        if user_id is None:
            return
        home = transaction_info(session).scope.home
        await watch.apply(session, user_id, await watch.limit(home, user_id))

    return (
        EventSubscription(
            consumer="files.quota_follows_plan",
            event=SubscriptionChanged,
            queue=TaskQueue.DEFAULT,
            deadline=DEADLINE,
            handle=follow_plan,
        ),
    )
