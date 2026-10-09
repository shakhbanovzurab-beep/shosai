"""Task declarations: name, queue, payload, deadline and retry policy (§4.3, §12, §14 rule 9).

A slice declares each task once, as a module constant; producers send by the declaration
and composition binds a handler to it with the process's resources. Nothing has a default
that matters: a task without a deadline would hold a worker forever, an implicit queue
would put bulk work next to email, and a generated name would orphan queued messages when
a module moves (draft lessons).
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.kv.locks import LockUnavailableError
from shosai.core.storage.errors import StorageUnavailableError
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.core.tasks.payloads import TaskPayload
from shosai.core.tasks.queues import TaskQueue

# Имя — «срез.задача»: адрес сообщений в потоке, ключ маркера такта и метка метрик.
TASK_NAME: Final = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")
TASK_NAME_MAX_LENGTH: Final = 64
# §4.3: брокер выдаёт сообщение не больше пяти раз, потом — dead letter с тревогой.
MAX_DELIVERIES: Final = 5
# Самая долгая работа черновика — выгрузка аккаунта — укладывалась в час.
MAX_DEADLINE: Final = timedelta(hours=1)
# Сверх дедлайна: столько аренда сообщения ещё продлевается, пока задача завершается.
HOLD_GRACE: Final = timedelta(seconds=60)

# Сбои, после которых следующая выдача может пройти: база дома, хранилище, Valkey, сеть,
# дедлайн. Ошибка в данных или в логике повтором не лечится.
TRANSIENT_FAILURES: Final[tuple[type[Exception], ...]] = (
    HomeUnavailableError,
    StorageUnavailableError,
    LockUnavailableError,
    TaskQueueUnavailableError,
    RedisConnectionError,
    RedisTimeoutError,
    ConnectionError,
    TimeoutError,
)


class TaskKind(StrEnum):
    """What a failure of the task means."""

    # Адресная работа (письмо, выгрузка): повторы по политике, затем dead letter.
    WORK = "work"
    # Такт обхода выбирает работу по состоянию: его провал повторит следующий такт, поэтому
    # он не повторяется и не попадает в dead letter (урок черновика: 1169 тактов в отстойнике).
    TICK = "tick"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How many deliveries a task may get and which failures earn the next one."""

    max_deliveries: int
    retry_on: tuple[type[Exception], ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= self.max_deliveries <= MAX_DELIVERIES:
            message = f"число выдач задачи — от 1 до {MAX_DELIVERIES}"
            raise ValueError(message)
        if (self.max_deliveries > 1) != bool(self.retry_on):
            message = "повтор задаётся вместе с ошибками, после которых он имеет смысл"
            raise ValueError(message)

    def allows_another(self, error: BaseException, delivery: int) -> bool:
        """Whether delivery number `delivery`, which failed with `error`, earns another one."""
        return delivery < self.max_deliveries and isinstance(error, self.retry_on)


# Повтор неидемпотентной задачи — второе письмо или второе списание: по умолчанию его нет.
NO_RETRY: Final = RetryPolicy(max_deliveries=1)
RETRY_TRANSIENT: Final = RetryPolicy(max_deliveries=MAX_DELIVERIES, retry_on=TRANSIENT_FAILURES)


@dataclass(frozen=True, slots=True)
class TaskDeclaration[P: TaskPayload]:
    """One task: its stable name, queue, payload model, deadline and retry policy."""

    name: str
    queue: TaskQueue
    payload: type[P]
    deadline: timedelta
    retry: RetryPolicy
    kind: TaskKind = TaskKind.WORK

    def __post_init__(self) -> None:
        if len(self.name) > TASK_NAME_MAX_LENGTH or not TASK_NAME.fullmatch(self.name):
            message = "имя задачи — «срез.задача» в snake_case, не длиннее 64 символов"
            raise ValueError(message)
        if not timedelta(0) < self.deadline <= MAX_DEADLINE:
            message = f"дедлайн задачи {self.name} — больше нуля и не больше часа"
            raise ValueError(message)
        if self.kind is TaskKind.TICK and self.retry.max_deliveries != 1:
            message = f"такт {self.name} не повторяется: его работу сделает следующий такт"
            raise ValueError(message)

    @property
    def hold_limit(self) -> timedelta:
        """How long a worker may hold one delivery: the deadline and a grace to settle it."""
        return self.deadline + HOLD_GRACE


@dataclass(frozen=True, slots=True)
class TaskHandler[P: TaskPayload]:
    """A declaration bound to the function that does its work in this process."""

    task: TaskDeclaration[P]
    handle: Callable[[P], Awaitable[None]]
