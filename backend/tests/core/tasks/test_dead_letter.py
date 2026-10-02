"""Dead-letter entries keep what diagnosis needs and no secret, within 32 KB."""

import json
from typing import Any

from pydantic import SecretStr
from taskiq import TaskiqMessage

from tests.core.tasks.workbench import Probe, declare
from whisperer.core.tasks.dead_letter import (
    ENTRY_LIMIT_BYTES,
    ERROR_TEXT_LIMIT,
    DeadLetterReason,
    failed_entry,
    unknown_entry,
    unparseable_entry,
)
from whisperer.core.tasks.declaration import NO_RETRY, TaskDeclaration
from whisperer.core.tasks.messages import REQUEST_ID_LABEL, TRACEPARENT_LABEL
from whisperer.core.tasks.payloads import TaskPayload
from whisperer.core.tasks.queues import TaskQueue

TASK = declare("probe.dead_letter")


class Credentials(TaskPayload):
    """A payload that carries a key in a plain field, against the rules."""

    note: str
    api_token: str


CREDENTIALS = TaskDeclaration(
    name="probe.credentials",
    queue=TaskQueue.DEFAULT,
    payload=Credentials,
    deadline=TASK.deadline,
    retry=NO_RETRY,
)
TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
LINK = "https://whisperer.one/reset?token=very-secret"


def message(payload: object, task_name: str = TASK.name, **labels: str) -> TaskiqMessage:
    """A message of a task as the stream holds it."""
    return TaskiqMessage(
        task_id="01920000000070008000000000000001",
        task_name=task_name,
        labels=labels,
        args=[],
        kwargs={"payload": payload},
    )


def decoded(text: str) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(text)
    return value


def test_a_failed_entry_keeps_the_task_the_error_and_the_ids() -> None:
    sent = Probe(note="отчёт").model_dump(mode="json")
    labels = {TRACEPARENT_LABEL: f"00-{TRACE_ID}-00f067aa0ba902b7-01", REQUEST_ID_LABEL: "req-1"}

    entry = failed_entry(
        TASK, message(sent, **labels), DeadLetterReason.FAILED, 5, ConnectionError("нет связи")
    )
    stored = decoded(entry.encode())

    assert stored["v"] == 1
    assert stored["queue"] == "default"
    assert stored["reason"] == "failed"
    assert stored["task"] == TASK.name
    assert stored["task_id"] == "01920000000070008000000000000001"
    assert stored["deliveries"] == 5
    assert stored["error_type"] == "builtins.ConnectionError"
    assert stored["error"] == "нет связи"
    assert stored["trace_id"] == TRACE_ID
    assert stored["request_id"] == "req-1"
    assert stored["payload"] == {"note": "отчёт", "link": None}
    assert stored["payload_masked"] is False
    assert stored["failed_at"].endswith("+00:00")


def test_a_task_secret_is_masked() -> None:
    sent = Probe(note="сброс", link=SecretStr(LINK)).model_dump(mode="json")

    entry = failed_entry(TASK, message(sent), DeadLetterReason.FAILED, 1, ValueError("x"))
    text = entry.encode()

    assert decoded(text)["payload"] == {"note": "сброс", "link": "***"}
    assert decoded(text)["payload_masked"] is True
    assert "very-secret" not in text


def test_a_value_under_a_sensitive_key_is_redacted_too() -> None:
    sent = Credentials(note="ключ", api_token="sk-1").model_dump(mode="json")

    entry = failed_entry(
        CREDENTIALS, message(sent, CREDENTIALS.name), DeadLetterReason.FAILED, 1, ValueError()
    )

    assert entry.payload == {"note": "ключ", "api_token": "***"}
    assert entry.payload_masked is True
    assert "sk-1" not in entry.encode()


def test_a_payload_that_does_not_match_its_declaration_is_not_kept() -> None:
    entry = failed_entry(TASK, message({"password": "p4ss"}), DeadLetterReason.FAILED, 1, None)

    assert entry.payload is None
    assert "p4ss" not in entry.encode()


def test_an_abandoned_entry_has_no_error() -> None:
    sent = Probe(note="долго").model_dump(mode="json")

    stored = decoded(failed_entry(TASK, message(sent), DeadLetterReason.ABANDONED, 5).encode())

    assert stored["reason"] == "abandoned"
    assert stored["error_type"] is None
    assert stored["error"] is None


def test_the_error_text_is_bounded() -> None:
    entry = failed_entry(TASK, message({}), DeadLetterReason.FAILED, 1, RuntimeError("x" * 5000))

    assert len(entry.error or "") == ERROR_TEXT_LIMIT


def test_an_unknown_task_keeps_its_name_but_never_its_payload() -> None:
    unknown = message({"email": "user@example.com"}, "gone.task")

    stored = decoded(unknown_entry(TaskQueue.BULK, unknown, 1).encode())

    assert stored["reason"] == "unknown_task"
    assert stored["queue"] == "bulk"
    assert stored["task"] == "gone.task"
    assert stored["payload"] is None
    assert stored["payload_dropped"] is True
    assert "user@example.com" not in json.dumps(stored)


def test_a_message_that_is_not_a_task_is_recorded_without_a_body() -> None:
    stored = decoded(unparseable_entry(TaskQueue.CRITICAL, 2).encode())

    assert stored["reason"] == "unparseable"
    assert stored["task"] == ""
    assert stored["deliveries"] == 2
    assert stored["payload"] is None


def test_an_entry_over_32_kb_drops_its_payload_and_keeps_the_rest() -> None:
    sent = Probe(note="ж" * ENTRY_LIMIT_BYTES).model_dump(mode="json")

    text = failed_entry(TASK, message(sent), DeadLetterReason.FAILED, 3, OSError("диск")).encode()

    assert len(text.encode()) <= ENTRY_LIMIT_BYTES
    assert decoded(text)["payload"] is None
    assert decoded(text)["payload_dropped"] is True
    assert decoded(text)["error"] == "диск"
