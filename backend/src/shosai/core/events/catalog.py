"""The events and subscriptions of the backend, listed explicitly by composition.

The catalog is built from explicit lists, never from whatever classes happen to be
imported. It refuses a second class for one event type, a second subscription with one
consumer name and a subscription to an event that is not listed. For each event type it
gives the routes the relay queues: one delivery task per subscriber. An event type
listed without subscribers is a fact nobody consumes yet; an event type that is not
listed at all cannot be written, and the relay holds back rows of such a type written by
a newer image.

The event classes are known before any slice is built (`EventTypes`): the outbox slices
write through needs only them, while subscriptions are built later, with the process's
services, and complete the catalog.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from shosai.core.events.delivery import EventDeliveryPayload, delivery_task
from shosai.core.events.domain_event import DomainEvent
from shosai.core.events.subscriptions import EventSubscription
from shosai.core.tasks.declaration import TaskDeclaration


@dataclass(frozen=True, slots=True)
class DeliveryRoute:
    """A subscription and the task the relay queues for it."""

    subscription: EventSubscription[Any]
    task: TaskDeclaration[EventDeliveryPayload]


class EventTypes:
    """Every event class of the backend, one class per event type."""

    def __init__(self, events: Sequence[type[DomainEvent]]) -> None:
        classes: dict[str, type[DomainEvent]] = {}
        for event in events:
            if event.event_type in classes:
                message = f"тип события {event.event_type} объявлен двумя классами"
                raise ValueError(message)
            classes[event.event_type] = event
        self.classes: Mapping[str, type[DomainEvent]] = MappingProxyType(classes)

    def lists(self, event: DomainEvent) -> bool:
        """Whether the event's class is the one listed for its type."""
        return self.classes.get(event.event_type) is type(event)


class EventCatalog:
    """Every event class and subscription of the backend, checked once at start."""

    def __init__(
        self,
        events: Sequence[type[DomainEvent]],
        subscriptions: Sequence[EventSubscription[Any]],
    ) -> None:
        self._types = EventTypes(events)
        classes = self._types.classes
        routes: dict[str, list[DeliveryRoute]] = {event_type: [] for event_type in classes}
        consumers: set[str] = set()
        for subscription in subscriptions:
            if subscription.consumer in consumers:
                message = f"потребитель {subscription.consumer} подписан дважды"
                raise ValueError(message)
            consumers.add(subscription.consumer)
            event_type = subscription.event.event_type
            if classes.get(event_type) is not subscription.event:
                message = f"потребитель {subscription.consumer} ждёт событие вне каталога"
                raise ValueError(message)
            routes[event_type].append(DeliveryRoute(subscription, delivery_task(subscription)))
        self._routes = MappingProxyType(
            {event_type: tuple(found) for event_type, found in routes.items()}
        )

    def lists(self, event: DomainEvent) -> bool:
        """Whether the event's class is the one listed for its type."""
        return self._types.lists(event)

    def routes_of(self, event_type: str) -> tuple[DeliveryRoute, ...] | None:
        """The delivery routes of an event type; None for a type this catalog does not list."""
        return self._routes.get(event_type)

    def all_routes(self) -> tuple[DeliveryRoute, ...]:
        """Every delivery route, for registering the delivery tasks in every role."""
        return tuple(route for found in self._routes.values() for route in found)
