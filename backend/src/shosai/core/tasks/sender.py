"""Sending tasks: the one way a slice queues work (target architecture §4.3, §12).

A slice receives the sender by injection and sends by a declaration and its payload. A
send waits for Valkey at most 50 ms; when Valkey is silent or the stream is full, the send
fails with `TaskQueueUnavailableError` (503 for a request) instead of waiting or losing
the task. A periodic task goes through `send_tick`, which skips the tick while the
previous one is in flight.
"""

from collections.abc import Coroutine, Mapping
from typing import Any

import structlog
from taskiq.exceptions import SendTaskError
from taskiq.kicker import AsyncKicker

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.observability.log_context import bound_request_id
from shosai.core.tasks.broker import ValkeyStreamBroker, new_task_id
from shosai.core.tasks.declaration import TaskDeclaration, TaskKind
from shosai.core.tasks.errors import TaskQueueUnavailableError, UnregisteredTaskError
from shosai.core.tasks.messages import PAYLOAD_ARGUMENT, REQUEST_ID_LABEL, TICK_LABEL
from shosai.core.tasks.metrics import TaskMetrics
from shosai.core.tasks.payloads import TaskPayload
from shosai.core.tasks.queues import TaskQueue, tick_key
from shosai.core.tasks.ticks import TickMarkers

log = structlog.stdlib.get_logger(__name__)


class TaskSender:
    """Queues tasks of every queue; slices receive it by injection."""

    def __init__(
        self,
        brokers: Mapping[TaskQueue, ValkeyStreamBroker],
        ticks: TickMarkers,
        metrics: TaskMetrics,
    ) -> None:
        self._brokers = brokers
        self._ticks = ticks
        self._metrics = metrics

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Queue one run of the task; return its task id."""
        if task.kind is TaskKind.TICK:
            message = f"такт {task.name} ставится через send_tick"
            raise ValueError(message)
        return await self._kick(task, payload, {}, new_task_id())

    async def send_tick[P: TaskPayload](
        self, task: TaskDeclaration[P], payload: P, *marker: str
    ) -> bool:
        """Queue a tick unless the previous one with the same marker is in flight.

        `marker` tells apart ticks of one task that may run side by side, such as the
        outbox relay of each home: `send_tick(RELAY, payload, home.value)`.
        """
        if task.kind is not TaskKind.TICK:
            message = f"задача {task.name} — не такт: она ставится через send"
            raise ValueError(message)
        key = tick_key(task.name, *marker)
        task_id = new_task_id()
        try:
            marked = await self._ticks.mark(key, task_id, task.hold_limit)
        except REDIS_FAILURES as error:
            self._metrics.count_send_failure(task.queue, "unavailable")
            raise TaskQueueUnavailableError(task.queue) from error
        if not marked:
            self._metrics.count_tick_skipped(task.name)
            log.info("Такт пропущен: предыдущий ещё в работе", task_name=task.name)
            return False
        try:
            await self._kick(task, payload, {TICK_LABEL: ":".join(marker)}, task_id)
        except TaskQueueUnavailableError:
            # Такта в полёте нет, и следующий не должен ждать истечения маркера.
            await self._ticks.release(key, task_id)
            raise
        return True

    async def _kick[P: TaskPayload](
        self, task: TaskDeclaration[P], payload: P, labels: dict[str, Any], task_id: str
    ) -> str:
        broker = self._brokers[task.queue]
        if broker.declaration(task.name) is not task:
            raise UnregisteredTaskError(task.name)
        if not isinstance(payload, task.payload):
            message = f"данные задачи {task.name} — не {task.payload.__name__}"
            raise TypeError(message)
        request_id = bound_request_id()
        if request_id is not None:
            labels[REQUEST_ID_LABEL] = request_id
        kicker: AsyncKicker[..., Coroutine[Any, Any, None]] = AsyncKicker(
            task_name=task.name, broker=broker, labels=labels
        )
        try:
            await kicker.with_task_id(task_id).kiq(
                **{PAYLOAD_ARGUMENT: payload.model_dump(mode="json")}
            )
        except SendTaskError as error:
            # Брокер уже посчитал отказ и записал его в лог.
            raise TaskQueueUnavailableError(task.queue) from error
        self._metrics.count_sent(task.queue, task.name)
        return task_id
