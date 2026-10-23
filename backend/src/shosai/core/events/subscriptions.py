"""Subscriptions: a slice's handler of another slice's event (target architecture §12).

A subscription names its consumer once and for ever: the name is the key of the delivery
marks and of the delivery task, so a renamed consumer would apply every recent event
again. The handler receives the session of the delivery's transaction and writes its
effect there; the mark is written in the same transaction, so a redelivered event
changes nothing. Like every transaction, it holds no external call (§14 rule 1): work that
calls outside goes to a task or a row the slice processes later.

The transaction runs in the event's home, unless the subscription names the home its
effect lives in — the EU home for the directory and the platform's own tables (ADR 0005,
F1 audit A7). Then the mark is written there too, beside the effect, so the two still
commit together; the event's account and company stay in the scope. Nothing personal
crosses homes: an event carries ids, numbers, flags, times and codes only.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.domain_event import DomainEvent
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import TASK_NAME_MAX_LENGTH
from shosai.core.tasks.queues import TaskQueue

# Задача доставки — «events.<потребитель>»: имя задачи не длиннее 64 символов.
DELIVERY_TASK_PREFIX: Final = "events."
CONSUMER_NAME: Final = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")
CONSUMER_NAME_MAX_LENGTH: Final = TASK_NAME_MAX_LENGTH - len(DELIVERY_TASK_PREFIX)


@dataclass(frozen=True, slots=True)
class ReceivedEvent[E: DomainEvent]:
    """An event as its consumer receives it: the fact, its id, version, time and scope.

    `scope` is the event's own: its home is where the event was written, which differs
    from the transaction's home for a subscription that names another one.
    """

    event: E
    event_id: UUID
    # Версия, которую записал производитель: старше или новее класса в этом образе.
    version: int
    occurred_at: datetime
    scope: TenancyScope


type EventHandler[E: DomainEvent] = Callable[[AsyncSession, ReceivedEvent[E]], Awaitable[None]]
# Чьи строки пишет эффект: человек и компания из самого события, в доме события.
type ScopeOfEvent[E: DomainEvent] = Callable[[E, TenancyScope], TenancyScope]


@dataclass(frozen=True, slots=True)
class EventSubscription[E: DomainEvent]:
    """A consumer of one event type: its stable name, queue, deadline, handler, home, scope.

    `home` is where the effect and its delivery mark live; None means the event's home.
    `scope` names, from the event, the person and company whose rows the effect writes —
    a departed member and the workspace they left — when they are not the event's own:
    row-level security then admits exactly those rows, in the delivery's one transaction.
    None keeps the event's scope.
    """

    consumer: str
    event: type[E]
    queue: TaskQueue
    deadline: timedelta
    handle: EventHandler[E]
    home: Home | None = None
    scope: ScopeOfEvent[E] | None = None

    def __post_init__(self) -> None:
        if len(self.consumer) > CONSUMER_NAME_MAX_LENGTH or not CONSUMER_NAME.fullmatch(
            self.consumer
        ):
            message = (
                "имя потребителя — «срез.потребитель» в snake_case, "
                f"не длиннее {CONSUMER_NAME_MAX_LENGTH} символов"
            )
            raise ValueError(message)

    def effect_scope(self, received: ReceivedEvent[E]) -> TenancyScope:
        """The scope of the delivery's transaction: the event's, or the one `scope` names from
        it, moved to the effect's home."""
        scope = received.scope if self.scope is None else self.scope(received.event, received.scope)
        if scope.home is not received.scope.home:
            message = "область эффекта называет человека и компанию, а дом — только `home`"
            raise ValueError(message)
        return scope if self.home is None else replace(scope, home=self.home)

    @property
    def task_name(self) -> str:
        """The name of the task that delivers the event to this consumer."""
        return DELIVERY_TASK_PREFIX + self.consumer
