"""The shape of a task message in the stream: TaskIQ's message with our labels.

A message carries one keyword argument, the payload as JSON, and labels: the W3C trace
context (§16.2), the `request_id` of the request that sent it and, for a periodic task,
its tick marker. Labels hold ids and codes only.
"""

import re
from collections.abc import Mapping
from typing import Final

from pydantic import ValidationError
from taskiq import TaskiqMessage

PAYLOAD_ARGUMENT: Final = "payload"
REQUEST_ID_LABEL: Final = "request_id"
TICK_LABEL: Final = "tick_marker"
TRACEPARENT_LABEL: Final = "traceparent"
TRACEPARENT: Final = re.compile(r"[0-9a-f]{2}-(?P<trace_id>[0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}")


def parse_message(data: bytes | None) -> TaskiqMessage | None:
    """The TaskIQ message in a stream entry, or None when the entry is not one.

    TaskIQ's receiver would log an unparseable body at WARNING, payload included; such an
    entry never reaches it.
    """
    if data is None:
        return None
    try:
        return TaskiqMessage.model_validate_json(data)
    except ValidationError:
        return None


def label_text(labels: Mapping[str, object], name: str) -> str | None:
    """A label's value as text, if the message has it."""
    value = labels.get(name)
    return value if isinstance(value, str) and value else None


def trace_id_of(labels: Mapping[str, object]) -> str | None:
    """The trace id from the message's W3C trace context, if it carries one."""
    traceparent = label_text(labels, TRACEPARENT_LABEL)
    found = TRACEPARENT.fullmatch(traceparent) if traceparent is not None else None
    return found.group("trace_id") if found else None
