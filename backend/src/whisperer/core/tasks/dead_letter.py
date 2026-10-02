"""Dead-letter entries: what is kept about a task that will not run again by itself (inv-8).

An entry keeps what an engineer needs to understand the failure and, if the payload was
complete, to send the task again: the task, the delivery count, the error, the trace and
request ids and the payload. Secrets do not enter it: `TaskSecret` fields are masked and
values under sensitive keys are redacted, and an entry with a masked value cannot be
replayed as it is (draft lesson: password-reset links lay in the dead letter for a week).
A payload that does not match its declaration, or belongs to an unknown task, is not kept:
which of its fields are secret is unknown. An entry is at most 32 KB, because Valkey does
not evict and the queues need that memory.
"""

import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final

from pydantic import ValidationError
from taskiq import TaskiqMessage

from whisperer.core.observability.redaction import redact_value
from whisperer.core.tasks.declaration import TaskDeclaration
from whisperer.core.tasks.messages import (
    PAYLOAD_ARGUMENT,
    REQUEST_ID_LABEL,
    label_text,
    trace_id_of,
)
from whisperer.core.tasks.payloads import MASK_SECRETS
from whisperer.core.tasks.queues import TaskQueue

ENTRY_LIMIT_BYTES: Final = 32 * 1024
ERROR_TEXT_LIMIT: Final = 500
TASK_NAME_LIMIT: Final = 64
ENTRY_VERSION: Final = 1


class DeadLetterReason(StrEnum):
    """Why a task is in the dead letter."""

    # Задача выполнилась и упала на последней разрешённой выдаче или ошибкой без повтора.
    FAILED = "failed"
    # Выдавалась столько раз, сколько разрешено, и ни разу не завершилась: воркер умирал.
    ABANDONED = "abandoned"
    # Задачи с таким именем нет в реестре воркера: производитель обогнал потребителя.
    UNKNOWN_TASK = "unknown_task"
    UNPARSEABLE = "unparseable"


@dataclass(frozen=True, slots=True)
class DeadLetterEntry:
    """One dead-letter entry; `encode` gives the JSON stored in the queue's dead letter."""

    queue: TaskQueue
    reason: DeadLetterReason
    task: str
    task_id: str | None
    deliveries: int
    failed_at: datetime
    error_type: str | None = None
    error: str | None = None
    trace_id: str | None = None
    request_id: str | None = None
    payload: object = None
    payload_masked: bool = False
    payload_dropped: bool = False

    def encode(self) -> str:
        """The entry as JSON within 32 KB; a larger payload is dropped, the rest is kept."""
        text = self._json()
        if len(text.encode()) <= ENTRY_LIMIT_BYTES:
            return text
        return replace(self, payload=None, payload_dropped=True)._json()

    def _json(self) -> str:
        fields: dict[str, Any] = {"v": ENTRY_VERSION, **asdict(self)}
        fields["failed_at"] = self.failed_at.isoformat()
        return json.dumps(fields, ensure_ascii=False, separators=(",", ":"))


def failed_entry(
    task: TaskDeclaration[Any],
    message: TaskiqMessage,
    reason: DeadLetterReason,
    deliveries: int,
    error: BaseException | None = None,
) -> DeadLetterEntry:
    """The entry of a known task that failed or was abandoned."""
    payload, masked = kept_payload(task, message)
    return DeadLetterEntry(
        queue=task.queue,
        reason=reason,
        task=task.name,
        task_id=message.task_id,
        deliveries=deliveries,
        failed_at=datetime.now(UTC),
        error_type=None if error is None else qualified_name(error),
        error=None if error is None else str(error)[:ERROR_TEXT_LIMIT],
        trace_id=trace_id_of(message.labels),
        request_id=label_text(message.labels, REQUEST_ID_LABEL),
        payload=payload,
        payload_masked=masked,
    )


def unknown_entry(queue: TaskQueue, message: TaskiqMessage, deliveries: int) -> DeadLetterEntry:
    """The entry of a message whose task the worker does not know; its payload is not kept."""
    return DeadLetterEntry(
        queue=queue,
        reason=DeadLetterReason.UNKNOWN_TASK,
        task=message.task_name[:TASK_NAME_LIMIT],
        task_id=message.task_id,
        deliveries=deliveries,
        failed_at=datetime.now(UTC),
        trace_id=trace_id_of(message.labels),
        request_id=label_text(message.labels, REQUEST_ID_LABEL),
        payload_dropped=True,
    )


def unparseable_entry(queue: TaskQueue, deliveries: int) -> DeadLetterEntry:
    """The entry of a stream message that is not a task message at all."""
    return DeadLetterEntry(
        queue=queue,
        reason=DeadLetterReason.UNPARSEABLE,
        task="",
        task_id=None,
        deliveries=deliveries,
        failed_at=datetime.now(UTC),
        payload_dropped=True,
    )


def kept_payload(task: TaskDeclaration[Any], message: TaskiqMessage) -> tuple[object, bool]:
    """The payload with secrets masked and redacted, and whether anything was hidden."""
    try:
        model = task.payload.model_validate(message.kwargs.get(PAYLOAD_ARGUMENT))
    except ValidationError:
        return None, False
    plain = model.model_dump(mode="json")
    masked = model.model_dump(mode="json", context={MASK_SECRETS: True})
    kept = redact_value(masked)
    return kept, kept != plain


def qualified_name(error: BaseException) -> str:
    """`module.Class` of an error: the type says what failed without the message's data."""
    kind = type(error)
    return f"{kind.__module__}.{kind.__qualname__}"
