"""The tasks of deletion: the due sweep, the erasure itself and the directory purge (ID-D5)."""

from datetime import UTC, datetime, timedelta
from typing import Any, Final

from shosai.core.account_data.handlers import AccountRef
from shosai.core.kernel.homes import Home
from shosai.core.schedule.jobs import DueRowSource, PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.core.tasks.sender import TaskSender
from shosai.features.identity.application.erasure import ERASE_ACCOUNT, Erasure
from shosai.features.identity.infrastructure.directory import Directory

# Освобождённый адрес хранится в каталоге 30 дней, потом строка уходит (§3.5).
DELETED_ADDRESS_KEPT: Final = timedelta(days=30)
ERASE_DUE: Final = TaskDeclaration(
    name="identity.erase_due",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=1),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PURGE_DIRECTORY: Final = TaskDeclaration(
    name="identity.purge_directory",
    queue=TaskQueue.BULK,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=5),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
DUE_SOURCES: Final = (DueRowSource(ERASE_DUE, every=timedelta(seconds=30)),)
# Каталог живёт только в доме ЕС.
DELETION_JOBS: Final = (PeriodicJob(PURGE_DIRECTORY, every=timedelta(days=1), homes=(Home.EU,)),)


def deletion_task_handlers(
    erasure: Erasure, directory: Directory, tasks: TaskSender
) -> tuple[TaskHandler[Any], ...]:
    """The deletion tasks bound to the process."""

    async def erase_due(payload: HomeTaskPayload) -> None:
        for user_id in await erasure.start_due(payload.home):
            await tasks.send(ERASE_ACCOUNT, HomeTaskPayload(home=payload.home, user_id=user_id))

    async def erase_account(payload: HomeTaskPayload) -> None:
        if payload.user_id is None:
            message = "задача стирания без аккаунта"
            raise ValueError(message)
        await erasure.erase(AccountRef(payload.user_id, payload.home))

    async def purge_directory(_payload: HomeTaskPayload) -> None:
        await directory.purge_deleted(datetime.now(UTC) - DELETED_ADDRESS_KEPT)

    return (
        TaskHandler(ERASE_DUE, erase_due),
        TaskHandler(ERASE_ACCOUNT, erase_account),
        TaskHandler(PURGE_DIRECTORY, purge_directory),
    )
