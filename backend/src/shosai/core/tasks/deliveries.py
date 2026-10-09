"""Deliveries held by this worker and how each one is settled when its run ends.

A delivery is held from admission until its settlement: acknowledged (finished, or a
failed tick whose work the next tick does), sent back for a later retry, moved to the dead
letter, or left pending when the run was interrupted, so that another worker takes it
after the lease. The decision is made from the run's outcome and the task's declaration.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from taskiq import TaskiqMessage

from shosai.core.tasks.dead_letter import DeadLetterEntry, DeadLetterReason, failed_entry
from shosai.core.tasks.declaration import TaskDeclaration, TaskKind
from shosai.core.tasks.metrics import RunOutcome
from shosai.core.tasks.timing import Backoff


@dataclass(frozen=True, slots=True)
class Acknowledge:
    """The run is over: remove the message from the queue."""


@dataclass(frozen=True, slots=True)
class RetryLater:
    """The run failed and another delivery may succeed after `delay`."""

    delay: timedelta


@dataclass(frozen=True, slots=True)
class MoveToDeadLetter:
    """The task will not run again by itself: keep the entry and remove the message."""

    entry: DeadLetterEntry


@dataclass(frozen=True, slots=True)
class LeavePending:
    """The run was interrupted (the worker stops): another worker takes it after the lease."""


type Settlement = Acknowledge | RetryLater | MoveToDeadLetter | LeavePending


@dataclass(slots=True)
class Delivery:
    """One delivery of a message to this worker."""

    stream_id: str
    task_id: str
    task: TaskDeclaration[Any]
    number: int
    taken_at: float
    started_at: float | None = None
    settlement: Settlement | None = None
    # Аренда продлевается, пока выдача у этого воркера; потерянная или переросшая предел — нет.
    renewing: bool = True


def decide(
    delivery: Delivery, message: TaskiqMessage, error: BaseException | None, backoff: Backoff
) -> tuple[Settlement, RunOutcome]:
    """How a finished run is settled and what its outcome is called in the metrics."""
    task = delivery.task
    if error is None:
        return Acknowledge(), "succeeded"
    # Остановка процесса — не провал задачи: она вернётся в работу после аренды.
    if not isinstance(error, Exception) or isinstance(error, asyncio.CancelledError):
        return LeavePending(), "interrupted"
    if task.kind is TaskKind.TICK:
        return Acknowledge(), "dropped"
    if task.retry.allows_another(error, delivery.number):
        return RetryLater(backoff.delay(delivery.number)), "retried"
    entry = failed_entry(task, message, DeadLetterReason.FAILED, delivery.number, error)
    return MoveToDeadLetter(entry), "dead_lettered"


class HeldDeliveries:
    """Deliveries of this worker not yet settled, by task id.

    A delivery stays here until its settlement even when its lease is lost or capped:
    the run goes on, and its outcome still settles the message as far as it may.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._held: dict[str, Delivery] = {}

    def __len__(self) -> int:
        return len(self._held)

    def take(self, delivery: Delivery) -> None:
        """Hold a delivery; a second delivery of a task held here is a mistake of the caller."""
        if delivery.task_id in self._held:
            message = f"выдача задачи {delivery.task_id} уже удерживается"
            raise ValueError(message)
        self._held[delivery.task_id] = delivery

    def get(self, task_id: str) -> Delivery | None:
        """The held delivery of a task, if any."""
        return self._held.get(task_id)

    def release(self, delivery: Delivery) -> None:
        """Forget a settled delivery."""
        if self._held.get(delivery.task_id) is delivery:
            del self._held[delivery.task_id]

    def lose(self, delivery: Delivery) -> bool:
        """Stop renewing a delivery another worker took; False if it was settled or not renewed."""
        if self._held.get(delivery.task_id) is not delivery or not delivery.renewing:
            return False
        delivery.renewing = False
        return True

    def due_for_renewal(self) -> tuple[list[Delivery], list[Delivery]]:
        """Deliveries whose lease to renew, and those just found held past their limit.

        A lease is renewed for the task's deadline and a grace; past that the worker has
        failed to settle the run, and the lease runs out so another worker can take it.
        """
        now = self._clock()
        renew: list[Delivery] = []
        capped: list[Delivery] = []
        for delivery in self._held.values():
            if not delivery.renewing:
                continue
            if now - delivery.taken_at > delivery.task.hold_limit.total_seconds():
                delivery.renewing = False
                capped.append(delivery)
            else:
                renew.append(delivery)
        return renew, capped
