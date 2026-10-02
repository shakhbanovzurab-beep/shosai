"""Subscriptions: a slice's handler of another slice's event (target architecture §12).

A subscription names its consumer once and for ever: the name is the key of the delivery
marks and of the delivery task, so a renamed consumer would apply every recent event
again. The handler receives the session of the delivery's transaction and writes its
effect there; the mark is written in the same transaction, so a redelivered event
changes nothing. The transaction runs in the event's home and tenancy scope. Like every
transaction, it holds no external call (§14 rule 1): work that calls outside goes to a
task or a row the slice processes later.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from whisperer.core.events.domain_event import DomainEvent
from whisperer.core.kernel.tenancy import TenancyScope
from whisperer.core.tasks.declaration import TASK_NAME_MAX_LENGTH
from whisperer.core.tasks.queues import TaskQueue

# Задача доставки — «events.<потребитель>»: имя задачи не длиннее 64 символов.
DELIVERY_TASK_PREFIX: Final = "events."
CONSUMER_NAME: Final = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")
CONSUMER_NAME_MAX_LENGTH: Final = TASK_NAME_MAX_LENGTH - len(DELIVERY_TASK_PREFIX)


@dataclass(frozen=True, slots=True)
class ReceivedEvent[E: DomainEvent]:
    """An event as its consumer receives it: the fact, its id, version, time and scope."""

    event: E
    event_id: UUID
    # Версия, которую записал производитель: старше или новее класса в этом образе.
    version: int
    occurred_at: datetime
    scope: TenancyScope


type EventHandler[E: DomainEvent] = Callable[[AsyncSession, ReceivedEvent[E]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class EventSubscription[E: DomainEvent]:
    """A consumer of one event type: its stable name, queue, deadline and handler."""

    consumer: str
    event: type[E]
    queue: TaskQueue
    deadline: timedelta
    handle: EventHandler[E]

    def __post_init__(self) -> None:
        if len(self.consumer) > CONSUMER_NAME_MAX_LENGTH or not CONSUMER_NAME.fullmatch(
            self.consumer
        ):
            message = (
                "имя потребителя — «срез.потребитель» в snake_case, "
                f"не длиннее {CONSUMER_NAME_MAX_LENGTH} символов"
            )
            raise ValueError(message)

    @property
    def task_name(self) -> str:
        """The name of the task that delivers the event to this consumer."""
        return DELIVERY_TASK_PREFIX + self.consumer
