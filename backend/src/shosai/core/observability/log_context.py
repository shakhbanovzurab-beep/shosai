"""Context carried by every log line of one unit of work (target architecture §16.2).

The fields live in context variables: each asyncio task sees its own values, and the
values never leak into a concurrent request or the next task a worker takes. Only the
fields of `LogFields` exist, so the set of log keys stays known and bounded.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypedDict, Unpack
from uuid import UUID

from structlog.contextvars import bind_contextvars, bound_contextvars, get_contextvars
from structlog.typing import EventDict, WrappedLogger

from shosai.core.kernel.homes import Home


class LogFields(TypedDict, total=False):
    """Fields a unit of work may add to its log lines; each is an id, never personal data."""

    request_id: str
    home: Home
    org_id: UUID
    user_id: UUID
    session_id: UUID
    task_name: str
    task_id: str
    event_id: UUID


@contextmanager
def log_context(**fields: Unpack[LogFields]) -> Iterator[None]:
    """Add the fields to every log line written inside the block; restore the outer ones after."""
    with bound_contextvars(**{key: str(value) for key, value in fields.items()}):
        yield


def bind_log_fields(**fields: Unpack[LogFields]) -> None:
    """Add the fields to every later log line of the current asyncio task.

    For a unit of work that owns its task, such as one task run in a worker: the values
    die with the task and never reach the next one.
    """
    bind_contextvars(**{key: str(value) for key, value in fields.items()})


def bound_request_id() -> str | None:
    """The `request_id` of the unit of work in progress, if it has one."""
    value = get_contextvars().get("request_id")
    return value if isinstance(value, str) else None


type FieldSource = Callable[[], LogFields]

_LATE_FIELDS: ContextVar[FieldSource | None] = ContextVar("shosai_late_log_fields", default=None)


@contextmanager
def late_log_fields(source: FieldSource) -> Iterator[None]:
    """Lines inside the block carry the fields `source` returns when each line is written.

    For ids a unit of work learns midway — a request's caller after authentication — so the
    lines written after that carry them, and nothing outlives the block.
    """
    token = _LATE_FIELDS.set(source)
    try:
        yield
    finally:
        _LATE_FIELDS.reset(token)


def merge_late_fields(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    """structlog processor: add the late fields the line does not already carry."""
    source = _LATE_FIELDS.get()
    if source is not None:
        for key, value in source().items():
            event_dict.setdefault(key, str(value))
    return event_dict
