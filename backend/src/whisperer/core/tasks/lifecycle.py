"""The run of a delivered task: its log context, its outcome, its settlement, its metrics.

One middleware on every broker, so no task can be added without being measured (draft
lesson: a wrapper per task is forgotten exactly on the task that later breaks). Each run
is one log line with its outcome and duration; a failure carries the stack. TaskIQ's own
line about the same exception is dropped by the logging pipeline (`core/observability`).
"""

import time
from collections.abc import Callable
from typing import Any

import structlog
from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult

from whisperer.core.observability.log_context import bind_log_fields
from whisperer.core.tasks.broker import ValkeyStreamBroker
from whisperer.core.tasks.declaration import TaskKind
from whisperer.core.tasks.deliveries import Delivery, RetryLater, decide
from whisperer.core.tasks.messages import REQUEST_ID_LABEL, TICK_LABEL, label_text
from whisperer.core.tasks.metrics import RunOutcome, TaskMetrics
from whisperer.core.tasks.queues import tick_key
from whisperer.core.tasks.ticks import TickMarkers

log = structlog.stdlib.get_logger(__name__)


class TaskLifecycle(TaskiqMiddleware):
    """Decides how each run of the broker's queue is settled and reports it."""

    def __init__(
        self,
        broker: ValkeyStreamBroker,
        metrics: TaskMetrics,
        ticks: TickMarkers,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self._held = broker.held
        self._queue = broker.queue
        self._backoff = broker.stream.timing.backoff
        self._metrics = metrics
        self._ticks = ticks
        self._clock = clock

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        """Start the run: its clock and the ids on its log lines."""
        delivery = self._held.get(message.task_id)
        if delivery is not None:
            delivery.started_at = self._clock()
        request_id = label_text(message.labels, REQUEST_ID_LABEL)
        if request_id is None:
            bind_log_fields(task_name=message.task_name, task_id=message.task_id)
        else:
            bind_log_fields(
                task_name=message.task_name, task_id=message.task_id, request_id=request_id
            )
        return message

    async def post_execute(self, message: TaskiqMessage, result: TaskiqResult[Any]) -> None:
        """Decide the settlement the receiver's acknowledgement will apply, and report the run."""
        delivery = self._held.get(message.task_id)
        if delivery is None:
            log.error("Выполнена задача, которой нет среди выдач воркера", queue=self._queue.value)
            return
        error = result.error if result.is_err else None
        settlement, outcome = decide(delivery, message, error, self._backoff)
        delivery.settlement = settlement
        started = delivery.started_at if delivery.started_at is not None else delivery.taken_at
        seconds = self._clock() - started
        self._metrics.observe_run(self._queue, delivery.task.name, outcome, seconds)
        self._report(delivery, outcome, seconds, error)
        if delivery.task.kind is TaskKind.TICK:
            await self._release_tick(delivery, message)

    def _report(
        self, delivery: Delivery, outcome: RunOutcome, seconds: float, error: BaseException | None
    ) -> None:
        fields: dict[str, Any] = {
            "queue": self._queue.value,
            "outcome": outcome,
            "delivery": delivery.number,
            "duration_ms": round(seconds * 1000, 1),
        }
        match outcome:
            case "succeeded":
                log.info("Задача выполнена", **fields)
            case "retried":
                if isinstance(delivery.settlement, RetryLater):
                    fields["retry_in_ms"] = round(delivery.settlement.delay.total_seconds() * 1000)
                log.warning("Задача упала и будет выдана снова", exc_info=error, **fields)
            case "dead_lettered":
                log.error("Задача упала и записана в dead letter", exc_info=error, **fields)
            case "dropped":
                log.warning("Такт упал: работу сделает следующий такт", exc_info=error, **fields)
            case "interrupted":
                log.warning("Задача прервана остановкой: вернётся в очередь после аренды", **fields)

    async def _release_tick(self, delivery: Delivery, message: TaskiqMessage) -> None:
        marker = message.labels.get(TICK_LABEL)
        if not isinstance(marker, str):
            return
        # Пустая метка — маркер такта без частей: `whisperer:tick:<задача>`.
        parts = marker.split(":") if marker else []
        try:
            key = tick_key(delivery.task.name, *parts)
        except ValueError:
            log.error("Метка маркера такта не разобрана: маркер снимется по сроку")
            return
        await self._ticks.release(key, message.task_id)
