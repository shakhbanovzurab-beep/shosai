"""Metrics of the task system (target architecture §16.4, §16.5, §16.6, §16.7).

Labels come from closed sets: the queue and the outcome are enums, a task name is one a
slice declared — a message with any other name is never admitted, so its name never
becomes a label. The queue gauges are global properties of Valkey and are set by one
process (the scheduler), not by every worker.
"""

from dataclasses import dataclass
from typing import Literal, Self

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from shosai.core.tasks.dead_letter import DeadLetterReason
from shosai.core.tasks.queues import TaskQueue

type RunOutcome = Literal["succeeded", "retried", "dead_lettered", "dropped", "interrupted"]
type SendFailure = Literal["full", "unavailable"]
type ValkeyOperation = Literal[
    "read", "claim", "renew", "acknowledge", "retry", "dead_letter", "prune", "group", "monitor"
]

# От десятков миллисекунд (письмо) до часа (выгрузка аккаунта).
RUN_BUCKETS = (0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 15.0, 60.0, 300.0, 900.0, 3600.0)
WAIT_BUCKETS = (0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 15.0, 60.0, 300.0, 900.0)
QUEUE_LABEL = ("queue",)


@dataclass(frozen=True, slots=True)
class QueueGauges:
    """Depth, oldest task and dead letter of every queue, set by `QueueMonitor`."""

    depth: Gauge
    oldest_age: Gauge
    dead_letter_entries: Gauge
    dead_letter_newest: Gauge

    @classmethod
    def register(cls, registry: CollectorRegistry) -> Self:
        """The gauges, registered in the process registry."""
        return cls(
            depth=Gauge(
                "shosai_task_queue_depth",
                "Невыполненные задачи в очереди",
                QUEUE_LABEL,
                registry=registry,
            ),
            oldest_age=Gauge(
                "shosai_task_queue_oldest_age_seconds",
                "Возраст самой старой невыполненной задачи очереди",
                QUEUE_LABEL,
                registry=registry,
            ),
            dead_letter_entries=Gauge(
                "shosai_task_dead_letter_entries",
                "Записи dead letter очереди за неделю",
                QUEUE_LABEL,
                registry=registry,
            ),
            dead_letter_newest=Gauge(
                "shosai_task_dead_letter_newest_timestamp_seconds",
                "Unix-время последней записи dead letter очереди; 0 — записей нет",
                QUEUE_LABEL,
                registry=registry,
            ),
        )


class TaskMetrics:
    """Counters and histograms of sending and running tasks, and the queue gauges."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._sent = Counter(
            "shosai_tasks_sent",
            "Задачи, поставленные в очередь",
            ("queue", "task"),
            registry=registry,
        )
        self._send_failures = Counter(
            "shosai_task_send_failures",
            "Постановки, отклонённые: поток полон или Valkey не ответил вовремя",
            ("queue", "reason"),
            registry=registry,
        )
        self._ticks_skipped = Counter(
            "shosai_task_ticks_skipped",
            "Такты, не поставленные, пока предыдущий такт того же обхода в работе",
            ("task",),
            registry=registry,
        )
        self._runs = Counter(
            "shosai_task_runs",
            "Выполнения задач по исходу",
            ("queue", "task", "outcome"),
            registry=registry,
        )
        self._run_seconds = Histogram(
            "shosai_task_run_duration_seconds",
            "Длительность выполнения задачи",
            ("queue", "task"),
            buckets=RUN_BUCKETS,
            registry=registry,
        )
        self._wait_seconds = Histogram(
            "shosai_task_wait_seconds",
            "Ожидание задачи в очереди до первой выдачи",
            QUEUE_LABEL,
            buckets=WAIT_BUCKETS,
            registry=registry,
        )
        self._dead_letters = Counter(
            "shosai_task_dead_letters",
            "Задачи, записанные в dead letter: сами они больше не выполнятся",
            ("queue", "reason"),
            registry=registry,
        )
        self._unknown = Counter(
            "shosai_task_unknown",
            "Сообщения с задачей, которой нет в реестре воркера",
            QUEUE_LABEL,
            registry=registry,
        )
        self._leases_lost = Counter(
            "shosai_task_leases_lost",
            "Сообщения, забранные у живого воркера: задача шла двумя прогонами",
            QUEUE_LABEL,
            registry=registry,
        )
        self._leases_capped = Counter(
            "shosai_task_leases_capped",
            "Сообщения, державшиеся дольше дедлайна с запасом: продление остановлено",
            QUEUE_LABEL,
            registry=registry,
        )
        self._valkey_failures = Counter(
            "shosai_task_valkey_failures",
            "Операции с очередями, на которые Valkey не ответил вовремя",
            ("queue", "operation"),
            registry=registry,
        )
        self.gauges = QueueGauges.register(registry)

    def count_sent(self, queue: TaskQueue, task: str) -> None:
        """One task queued."""
        self._sent.labels(queue=queue.value, task=task).inc()

    def count_send_failure(self, queue: TaskQueue, reason: SendFailure) -> None:
        """One task not queued."""
        self._send_failures.labels(queue=queue.value, reason=reason).inc()

    def count_tick_skipped(self, task: str) -> None:
        """One tick not queued because the previous one is still in flight."""
        self._ticks_skipped.labels(task=task).inc()

    def observe_run(
        self, queue: TaskQueue, task: str, outcome: RunOutcome, seconds: float | None = None
    ) -> None:
        """One settled delivery of a task: its outcome and, if it ran, its duration."""
        self._runs.labels(queue=queue.value, task=task, outcome=outcome).inc()
        if seconds is not None:
            self._run_seconds.labels(queue=queue.value, task=task).observe(seconds)

    def observe_wait(self, queue: TaskQueue, seconds: float) -> None:
        """How long a task waited in the queue before its first delivery."""
        self._wait_seconds.labels(queue=queue.value).observe(max(seconds, 0.0))

    def count_dead_letter(self, queue: TaskQueue, reason: DeadLetterReason) -> None:
        """One entry written to the dead letter."""
        self._dead_letters.labels(queue=queue.value, reason=reason.value).inc()

    def count_unknown(self, queue: TaskQueue) -> None:
        """One message whose task this worker does not know."""
        self._unknown.labels(queue=queue.value).inc()

    def count_lease_lost(self, queue: TaskQueue) -> None:
        """One message another worker took while this one still ran it."""
        self._leases_lost.labels(queue=queue.value).inc()

    def count_lease_capped(self, queue: TaskQueue) -> None:
        """One message held past its deadline and grace; its lease is no longer renewed."""
        self._leases_capped.labels(queue=queue.value).inc()

    def count_valkey_failure(self, queue: TaskQueue, operation: ValkeyOperation) -> None:
        """One queue operation Valkey did not answer in time."""
        self._valkey_failures.labels(queue=queue.value, operation=operation).inc()
