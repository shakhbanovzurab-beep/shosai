"""A business event becomes one queued alert, once, and only while alerting is on."""

import uuid
from dataclasses import dataclass, field
from datetime import date

from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.ai.events import UserSpendExceeded
from shosai.core.events.catalog import EventCatalog
from shosai.core.events.domain_event import DomainEvent
from shosai.core.events.metrics import EventMetrics
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.relay import OutboxRelay
from shosai.core.events.relay_limits import RelayLimits
from shosai.core.events.resources import EventResources
from shosai.core.events.system import event_task_handlers
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.payloads import TaskPayload
from shosai.features.alerting.channels.subscriptions import BusinessAlerts
from shosai.features.alerting.channels.tasks import POST_ALERT, AlertPayload
from shosai.features.billing.contracts.events import SalesInquiryReceived
from shosai.features.identity.contracts import AccountDeleted
from shosai.features.studio.contracts.events import STUDIO_EVENTS
from tests.core.events.relay_bench import RecordingSender
from tests.core.tasks.workbench import bound_workbench, eventually, running, settled
from tests.harness.database_access import DatabaseAccess

SITE = "https://shosai.tech"
USER_ID = uuid.UUID("0190f0f0-0000-7000-8000-0000000000a2")


@dataclass
class QueuedTasks:
    """The tasks the subscriptions queued, in order."""

    sent: list[tuple[str, TaskPayload]] = field(default_factory=list)

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Record the task instead of queueing it."""
        self.sent.append((task.name, payload))
        return str(len(self.sent))


def resources(homes: DatabaseAccess, alerts: BusinessAlerts) -> EventResources:
    """The business events and alerting's consumers over the run's slot."""
    events: list[type[DomainEvent]] = [
        UserSpendExceeded,
        AccountDeleted,
        SalesInquiryReceived,
        *STUDIO_EVENTS,
    ]
    return EventResources(
        catalog=EventCatalog(events, alerts.subscriptions()),
        transactions=homes.transactions,
        metrics=EventMetrics(CollectorRegistry()),
        tracer_provider=TracerProvider(),
        relay_limits=RelayLimits(),
    )


async def deliver_twice(
    valkey: Redis, homes: DatabaseAccess, alerts: BusinessAlerts, event: DomainEvent, home: Home
) -> None:
    """Write the event, relay it and deliver each of its routes twice, as a redelivery would."""
    events = resources(homes, alerts)
    async with homes.transactions.begin(TenancyScope(home, USER_ID, None)) as session:
        await EventOutbox(events.catalog).add(session, event)
    captured = RecordingSender(homes.databases)
    await OutboxRelay(events, captured).relay(home)
    registry = CollectorRegistry()
    bench = bound_workbench(valkey, lambda sender: event_task_handlers(events, sender), registry)
    async with running(bench.broker()):
        for task_name, delivery in captured.sent:
            [route] = [each for each in events.catalog.all_routes() if each.task.name == task_name]
            for _ in range(2):
                await bench.system.sender.send(route.task, delivery)
            await eventually(settled(bench, task_name, "succeeded", 2))


async def test_a_spend_event_delivered_twice_queues_one_ticket(
    valkey: Redis, homes: DatabaseAccess
) -> None:
    queued = QueuedTasks()
    event = UserSpendExceeded(
        user_id=USER_ID, day=date(2026, 10, 16), spend_micro_usd=25_000_000,
        threshold_micro_usd=20_000_000,
    )  # fmt: skip

    await deliver_twice(valkey, homes, BusinessAlerts(queued, SITE, enabled=True), event, Home.RU)

    [(task, payload)] = queued.sent
    assert task == POST_ALERT.name
    assert isinstance(payload, AlertPayload)
    assert (payload.home, payload.user_id) == (Home.RU, USER_ID)
    assert payload.alert.kind == "ai.user_spend.exceeded"
    assert payload.alert.admin_card == f"{SITE}/admin/users/{USER_ID}"


async def test_a_deletion_delivered_twice_queues_one_notice(
    valkey: Redis, homes: DatabaseAccess
) -> None:
    queued = QueuedTasks()
    alerts = BusinessAlerts(queued, SITE, enabled=True)

    await deliver_twice(valkey, homes, alerts, AccountDeleted(user_id=USER_ID), Home.EU)

    [(_, payload)] = queued.sent
    assert isinstance(payload, AlertPayload)
    assert (payload.alert.kind, payload.home) == ("identity.account.deleted", Home.EU)


async def test_with_alerting_off_the_event_is_accepted_and_nothing_is_queued(
    valkey: Redis, homes: DatabaseAccess
) -> None:
    queued = QueuedTasks()
    alerts = BusinessAlerts(queued, SITE, enabled=False)

    await deliver_twice(valkey, homes, alerts, AccountDeleted(user_id=USER_ID), Home.RU)

    assert queued.sent == []
