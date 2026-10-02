"""Errors of the task system that producers and handlers meet."""

from collections.abc import Sequence
from http import HTTPStatus
from typing import Final

from whisperer.core.kernel.errors import AppError
from whisperer.core.tasks.queues import TaskQueue

RETRY_AFTER_SECONDS: Final = 5


class TaskQueueUnavailableError(AppError):
    """The task was not queued: Valkey did not answer within 50 ms or the stream is full.

    A request answers 503 and the client retries (§4.3); work that must not be lost —
    money and email — goes through the outbox instead of a direct send.
    """

    def __init__(self, queue: TaskQueue) -> None:
        super().__init__(
            "queue_unavailable",
            HTTPStatus.SERVICE_UNAVAILABLE,
            params={"retry_after_seconds": RETRY_AFTER_SECONDS},
        )
        self.queue = queue


class InvalidTaskPayloadError(Exception):
    """A delivered payload does not match its declaration; another delivery cannot help.

    The message names the fields and the kind of each problem, never the values.
    """

    def __init__(self, task_name: str, problems: Sequence[str]) -> None:
        super().__init__(f"данные задачи {task_name} не прошли проверку: {'; '.join(problems)}")
        self.problems = tuple(problems)


class UnregisteredTaskError(Exception):
    """A task was sent that this process has no handler for: a composition mistake.

    Every role registers every task (draft lesson: a worker that did not know a task
    dropped it), so sending one that is not registered fails at once.
    """

    def __init__(self, task_name: str) -> None:
        super().__init__(f"задача {task_name} не зарегистрирована в этом процессе")
