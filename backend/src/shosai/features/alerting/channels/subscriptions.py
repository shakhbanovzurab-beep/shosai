"""Alerting's consumers: a business event becomes one queued alert (F5-D5).

The handler only queues the delivery task in the event's delivery transaction; the mark
written there makes a redelivered event queue nothing. With `ALERTING_ENABLED` off the
event is accepted and logged, and nothing is queued.
"""

from datetime import timedelta
from typing import Any, Final, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ai.events import UserSpendExceeded
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.payloads import TaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.alerting.channels.tasks import POST_ALERT, AlertPayload
from shosai.features.alerting.domain.alerts import (
    BusinessAlert,
    account_deleted,
    sales_inquiry,
    spend_exceeded,
)
from shosai.features.billing.contracts.events import SalesInquiryReceived
from shosai.features.identity.contracts import AccountDeleted

DEADLINE: Final = timedelta(seconds=30)
log = structlog.stdlib.get_logger(__name__)


class TaskQueueing(Protocol):
    """Queues a task; the process's `TaskSender`."""

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Queue one run of the task; return its task id."""
        ...


class BusinessAlerts:
    """Turns received events into queued alerts, or only logs them while alerting is off."""

    def __init__(self, tasks: TaskQueueing, site: str, *, enabled: bool) -> None:
        self._tasks = tasks
        self._site = site
        self._enabled = enabled

    async def raise_alert(self, received: ReceivedEvent[Any], alert: BusinessAlert) -> None:
        """Queue the alert of the event."""
        if not self._enabled:
            log.info("Оповещение не отправлено: ALERTING_ENABLED выключен", kind=alert.kind)
            return
        payload = AlertPayload(
            home=received.scope.home,
            user_id=received.scope.user_id,
            event_id=received.event_id,
            occurred_at=received.occurred_at,
            alert=alert,
        )
        await self._tasks.send(POST_ALERT, payload)

    async def spend_exceeded(
        self, session: AsyncSession, received: ReceivedEvent[UserSpendExceeded]
    ) -> None:
        """A ticket: one person's AI spend today passed the threshold."""
        del session
        event = received.event
        alert = spend_exceeded(
            self._site, event.user_id, event.day, event.spend_micro_usd, event.threshold_micro_usd
        )
        await self.raise_alert(received, alert)

    async def account_deleted(
        self, session: AsyncSession, received: ReceivedEvent[AccountDeleted]
    ) -> None:
        """A notice: a person's data is erased."""
        del session
        await self.raise_alert(received, account_deleted(self._site, received.event.user_id))

    async def sales_inquiry(
        self, session: AsyncSession, received: ReceivedEvent[SalesInquiryReceived]
    ) -> None:
        """A notice: a person asked sales about a custom-priced plan."""
        del session
        event = received.event
        await self.raise_alert(received, sales_inquiry(self._site, event.user_id, event.team_size))

    def subscriptions(self) -> tuple[EventSubscription[Any], ...]:
        """One consumer per event kind; the names are the keys of their delivery marks."""
        return (
            EventSubscription(
                consumer="alerting.user_spend_ticket",
                event=UserSpendExceeded,
                queue=TaskQueue.DEFAULT,
                deadline=DEADLINE,
                handle=self.spend_exceeded,
            ),
            EventSubscription(
                consumer="alerting.account_deleted_notice",
                event=AccountDeleted,
                queue=TaskQueue.DEFAULT,
                deadline=DEADLINE,
                handle=self.account_deleted,
            ),
            EventSubscription(
                consumer="alerting.sales_inquiry_notice",
                event=SalesInquiryReceived,
                queue=TaskQueue.DEFAULT,
                deadline=DEADLINE,
                handle=self.sales_inquiry,
            ),
        )
