"""The broker of one queue: TaskIQ's `AsyncBroker` over the process's Valkey client (ADR 0016).

Producers append to the queue's stream within 50 ms; a full stream or a silent Valkey
refuses the task instead of losing older ones. A worker reads one message at a time, so
another worker of the same queue is never starved by a batch held here (draft lesson),
and admits only what it can run: a message that is not a task, or whose task is unknown,
goes to the dead letter instead of TaskIQ's silent drop (§14 rule 9). Abandoned messages
are claimed again; a separate task renews the leases of held messages, so a busy worker
keeps its long tasks. Every Valkey failure is counted, logged at most once per interval
and waited out; it never stops the worker.
"""

import asyncio
import contextlib
import functools
import os
import secrets
import socket
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any

import structlog
from taskiq import AckableMessage, AsyncBroker, BrokerMessage, TaskiqMessage

from shosai.core.kernel.ids import new_id
from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.observability.outage_log import OutageLog
from shosai.core.tasks.dead_letter import (
    DeadLetterReason,
    failed_entry,
    unknown_entry,
    unparseable_entry,
)
from shosai.core.tasks.declaration import TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.deliveries import Delivery, HeldDeliveries
from shosai.core.tasks.handlers import RegisteredTask, handler_function
from shosai.core.tasks.messages import parse_message
from shosai.core.tasks.metrics import TaskMetrics, ValkeyOperation
from shosai.core.tasks.settling import DeliverySettler, QueueFailures
from shosai.core.tasks.stream import (
    ConsumerGroupMissingError,
    QueueFullError,
    StreamEntry,
    TaskStream,
)

log = structlog.stdlib.get_logger(__name__)


def new_task_id() -> str:
    """A time-ordered task id: UUIDv7 in hex."""
    return new_id().hex


def new_consumer_name() -> str:
    """A consumer name for one process: host, process id and a random part."""
    return f"{socket.gethostname()}-{os.getpid()}-{secrets.token_hex(4)}"


class ValkeyStreamBroker(AsyncBroker):
    """Sends tasks of one queue and, in a worker, delivers them to TaskIQ's receiver."""

    def __init__(
        self, stream: TaskStream, metrics: TaskMetrics, clock: Callable[[], float] = time.monotonic
    ) -> None:
        super().__init__()
        self.with_id_generator(new_task_id)
        self.queue = stream.queue
        self.stream = stream
        self.held = HeldDeliveries(clock)
        self._metrics = metrics
        self._clock = clock
        self._timing = stream.timing
        self._failures = QueueFailures(stream, metrics)
        self._settler = DeliverySettler(stream, metrics, self._failures)
        self._send_outages = OutageLog("Valkey не ответил: задача не поставлена")
        self._declarations: dict[str, TaskDeclaration[Any]] = {}
        self._renewal: asyncio.Task[None] | None = None

    def register(self, handler: TaskHandler[Any]) -> None:
        """Make the handler's task runnable by this queue's workers."""
        task = handler.task
        if task.queue is not self.queue:
            message = f"задача {task.name} объявлена для очереди {task.queue}, а не {self.queue}"
            raise ValueError(message)
        if task.name in self._declarations:
            message = f"задача {task.name} зарегистрирована дважды"
            raise ValueError(message)
        self._declarations[task.name] = task
        self.local_task_registry[task.name] = RegisteredTask(
            self, task.name, handler_function(handler)
        )

    def declaration(self, task_name: str) -> TaskDeclaration[Any] | None:
        """The registered declaration of a task, if this queue has it."""
        return self._declarations.get(task_name)

    async def startup(self) -> None:
        """In a worker, start renewing the leases of held messages."""
        await super().startup()
        if self.is_worker_process and self._renewal is None:
            self._renewal = asyncio.create_task(
                self._renew_forever(), name=f"task-leases:{self.queue}"
            )

    async def shutdown(self) -> None:
        """Stop renewing leases; messages still held return to the queue after the lease."""
        renewal, self._renewal = self._renewal, None
        if renewal is not None:
            renewal.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await renewal
        await super().shutdown()

    async def kick(self, message: BrokerMessage) -> None:
        """Append a task to the stream; count and log a refusal, then raise it."""
        try:
            await self.stream.enqueue(message.message)
        except QueueFullError:
            self._metrics.count_send_failure(self.queue, "full")
            log.error("Очередь задач заполнена: задача не поставлена", queue=self.queue.value)
            raise
        except REDIS_FAILURES as error:
            self._metrics.count_send_failure(self.queue, "unavailable")
            self._send_outages.failed(error, queue=self.queue.value)
            raise

    async def listen(self) -> AsyncGenerator[AckableMessage]:
        """Deliver messages one at a time: abandoned ones first, then new ones."""
        recover_at = prune_at = self._clock()
        while True:
            operation: ValkeyOperation = "prune"
            entry: StreamEntry | None = None
            try:
                now = self._clock()
                if now >= prune_at:
                    prune_at = now + self._timing.prune_consumers_every.total_seconds()
                    await self.stream.prune_consumers()
                operation = "claim"
                if now >= recover_at:
                    entry = await self.stream.claim_abandoned()
                    if entry is None:
                        recover_at = now + self._timing.recover_every.total_seconds()
                operation = "read"
                if entry is None:
                    entry = await self.stream.read()
            except ConsumerGroupMissingError:
                await self._recreate_group()
                continue
            except REDIS_FAILURES as error:
                await self._wait_out(operation, error)
                continue
            if entry is not None and (message := await self._admit(entry)) is not None:
                yield message

    async def renew_leases(self) -> None:
        """Renew the lease of every held message; report those another worker took."""
        renew, capped = self.held.due_for_renewal()
        for delivery in capped:
            self._metrics.count_lease_capped(self.queue)
            log.error(
                "Задача держится дольше дедлайна с запасом: аренда больше не продлевается",
                **self._fields(delivery.task, delivery.task_id),
            )
        if not renew:
            return
        try:
            kept = await self.stream.renew([delivery.stream_id for delivery in renew])
        except REDIS_FAILURES as error:
            self._failures.record("renew", error)
            return
        for delivery in renew:
            if delivery.stream_id not in kept and self.held.lose(delivery):
                self._metrics.count_lease_lost(self.queue)
                log.error(
                    "Сообщение забрал другой воркер: задача идёт вторым прогоном",
                    **self._fields(delivery.task, delivery.task_id),
                )

    async def _admit(self, entry: StreamEntry) -> AckableMessage | None:
        """The message for the receiver, or None when it was settled here instead."""
        message = parse_message(entry.data)
        if entry.data is None or message is None:
            record = unparseable_entry(self.queue, entry.delivery)
            await self._settler.dead_letter(entry.stream_id, record)
            return None
        task = self._declarations.get(message.task_name)
        if task is None:
            await self._unknown(entry, message)
            return None
        if self.held.get(message.task_id) is not None:
            # Задача ещё выполняется здесь, а аренду не успели продлить: её исход и решит
            # судьбу сообщения, второй прогон или dead letter были бы ошибкой.
            return None
        if entry.delivery > task.retry.max_deliveries:
            await self._abandoned(entry, task, message)
            return None
        delivery = Delivery(entry.stream_id, message.task_id, task, entry.delivery, self._clock())
        self.held.take(delivery)
        if entry.delivery == 1:
            self._metrics.observe_wait(self.queue, time.time() - entry.enqueued_at)
        return AckableMessage(data=entry.data, ack=functools.partial(self._settle, delivery))

    async def _unknown(self, entry: StreamEntry, message: TaskiqMessage) -> None:
        self._metrics.count_unknown(self.queue)
        log.error(
            "Задачи нет в реестре воркера: сообщение отправлено в dead letter",
            queue=self.queue.value,
            task_name=message.task_name[:64],
            task_id=message.task_id,
        )
        record = unknown_entry(self.queue, message, entry.delivery)
        await self._settler.dead_letter(entry.stream_id, record)

    async def _abandoned(
        self, entry: StreamEntry, task: TaskDeclaration[Any], message: TaskiqMessage
    ) -> None:
        """A message delivered as often as allowed that never finished: its worker died."""
        if task.kind is TaskKind.TICK:
            log.warning(
                "Такт брошен воркером и снят: работу сделает следующий такт",
                **self._fields(task, message.task_id),
            )
            self._metrics.observe_run(self.queue, task.name, "dropped")
            await self._settler.acknowledge(entry.stream_id)
            return
        log.error(
            "Задача ни разу не завершилась за разрешённые выдачи",
            **self._fields(task, message.task_id),
        )
        record = failed_entry(task, message, DeadLetterReason.ABANDONED, entry.delivery - 1)
        await self._settler.dead_letter(entry.stream_id, record)

    async def _settle(self, delivery: Delivery) -> None:
        """The receiver's acknowledgement: apply the settlement decided when the run ended."""
        self.held.release(delivery)
        await self._settler.settle(delivery)

    async def _recreate_group(self) -> None:
        """The group vanished (Valkey reset or failover): recreate it, or wait if Valkey is out."""
        log.warning("Группа потребителей очереди исчезла: создаётся заново", queue=self.queue.value)
        try:
            await self.stream.ensure_group()
        except REDIS_FAILURES as error:
            await self._wait_out("group", error)

    async def _renew_forever(self) -> None:
        while True:
            await asyncio.sleep(self._timing.renew_every.total_seconds())
            try:
                await self.renew_leases()
            except Exception:
                # Остановка продления отдала бы все долгие задачи соседям на второй прогон:
                # проход записан со стеком, следующий — через интервал.
                log.exception("Проход продления аренды упал", queue=self.queue.value)

    async def _wait_out(self, operation: ValkeyOperation, error: BaseException) -> None:
        self._failures.record(operation, error)
        await asyncio.sleep(self._timing.outage_pause.total_seconds())

    def _fields(self, task: TaskDeclaration[Any], task_id: str) -> dict[str, str]:
        return {"queue": self.queue.value, "task_name": task.name, "task_id": task_id}
