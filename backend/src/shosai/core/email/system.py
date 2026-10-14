"""The mail tasks of a process: the sweep and the purge of each home, and the send.

Every role registers them, like every other task (§14 rule 9). The scheduler queues the
sweep of each home every 2 s as a due-row source (F6-C10, F6-C14) and the purge once a day
as a periodic job; the sweep queues one send task per due mail.
"""

from datetime import timedelta
from typing import Any, Final

import structlog

from shosai.core.email.delivery import MailDelivery, SendEmailPayload, SendTasks
from shosai.core.schedule.jobs import DueRowSource, PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.errors import TaskQueueUnavailableError
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.core.tasks.sender import TaskSender

SWEEP_EVERY: Final = timedelta(seconds=2)
# Дедлайн обхода короче аренды захвата (60 с): соседний обход строки идущего не возьмёт.
SWEEP_EMAIL: Final = TaskDeclaration(
    name="email.sweep",
    queue=TaskQueue.CRITICAL,
    payload=HomeTaskPayload,
    deadline=timedelta(seconds=30),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
# Повтор — не доставкой задачи, а строкой: письмо снова в очереди с паузой (delivery.py).
SEND_TASKS: Final = SendTasks(
    critical=TaskDeclaration(
        name="email.send",
        queue=TaskQueue.CRITICAL,
        payload=SendEmailPayload,
        deadline=timedelta(minutes=2),
        retry=NO_RETRY,
    ),
    bulk=TaskDeclaration(
        name="email.send_newsletter",
        queue=TaskQueue.BULK,
        payload=SendEmailPayload,
        deadline=timedelta(minutes=2),
        retry=NO_RETRY,
    ),
)
PURGE_EMAIL: Final = TaskDeclaration(
    name="email.purge",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=10),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
EMAIL_SWEEP_SOURCE: Final = DueRowSource(SWEEP_EMAIL, SWEEP_EVERY)
PURGE_EMAIL_JOB: Final = PeriodicJob(PURGE_EMAIL, timedelta(days=1))
log = structlog.stdlib.get_logger(__name__)


def email_task_handlers(delivery: MailDelivery, sender: TaskSender) -> list[TaskHandler[Any]]:
    """The sweep, the two send tasks and the purge, bound to the process."""

    async def sweep(payload: HomeTaskPayload) -> None:
        for message_id, kind in await delivery.claim(payload.home):
            task = SEND_TASKS.of(kind)
            try:
                await sender.send(task, SendEmailPayload(home=payload.home, message_id=message_id))
            except TaskQueueUnavailableError:
                # Захват истечёт через минуту, и следующий обход поставит письмо снова.
                log.warning(
                    "Отправка письма не поставлена: очередь недоступна", home=payload.home.value
                )
                return

    async def send(payload: SendEmailPayload) -> None:
        await delivery.send(payload.home, payload.message_id)

    async def purge(payload: HomeTaskPayload) -> None:
        removed = await delivery.purge(payload.home)
        log.info("Отправленные письма старше недели удалены", home=payload.home.value, rows=removed)

    return [
        TaskHandler(SWEEP_EMAIL, sweep),
        TaskHandler(SEND_TASKS.critical, send),
        TaskHandler(SEND_TASKS.bulk, send),
        TaskHandler(PURGE_EMAIL, purge),
    ]
