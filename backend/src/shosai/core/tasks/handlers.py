"""How a bound handler becomes a task TaskIQ's receiver runs.

The receiver calls the registered function with the message's payload. The function
validates the payload against the declaration — the receiver's own parsing is off, because
it logs the rejected input — adds the payload's ids to the log lines of the run and runs
the handler within the deadline the consumer's declaration sets, whatever the message says.
"""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import ValidationError
from taskiq import AsyncBroker
from taskiq.decor import AsyncTaskiqDecoratedTask

from shosai.core.observability.log_context import bind_log_fields
from shosai.core.tasks.declaration import TaskDeclaration, TaskHandler
from shosai.core.tasks.errors import InvalidTaskPayloadError
from shosai.core.tasks.payloads import TaskPayload

type JsonObject = dict[str, object]
type TaskFunction = Callable[[JsonObject], Coroutine[Any, Any, None]]


class RegisteredTask(AsyncTaskiqDecoratedTask[[JsonObject], Coroutine[Any, Any, None]]):
    """A task in a broker's registry.

    TaskIQ's constructor renames the function and sets it as an attribute of its module,
    for process pools this backend does not use; that hidden side effect is skipped here.
    """

    def __init__(self, broker: AsyncBroker, task_name: str, function: TaskFunction) -> None:
        self.broker = broker
        self.task_name = task_name
        self.original_func = function
        self.labels: dict[str, Any] = {}
        self.return_type = None


def validation_problems(error: ValidationError) -> list[str]:
    """`field: kind` of each problem; the rejected values never enter the text."""
    return [
        f"{'.'.join(str(part) for part in item['loc']) or '<payload>'}: {item['type']}"
        for item in error.errors(include_url=False, include_input=False, include_context=False)
    ]


def parse_payload[P: TaskPayload](task: TaskDeclaration[P], payload: object) -> P:
    """The payload as the declared model; problems name fields and kinds, never values."""
    try:
        return task.payload.model_validate(payload)
    except ValidationError as error:
        raise InvalidTaskPayloadError(task.name, validation_problems(error)) from None


def handler_function(handler: TaskHandler[Any]) -> TaskFunction:
    """The function the receiver runs for one task: validate, add log fields, keep the deadline."""
    task = handler.task

    async def run_task(payload: JsonObject) -> None:
        model = parse_payload(task, payload)
        # Выдача идёт в своей задаче asyncio: поля доживут до строки об исходе прогона
        # (core/tasks/lifecycle.py) и не попадут в следующую выдачу.
        bind_log_fields(**model.log_fields())
        async with asyncio.timeout(task.deadline.total_seconds()):
            await handler.handle(model)

    return run_task
