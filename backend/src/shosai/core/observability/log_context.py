"""Context carried by every log line of one unit of work (target architecture §16.2).

The fields live in context variables: each asyncio task sees its own values, and the
values never leak into a concurrent request or the next task a worker takes. Only the
fields of `LogFields` exist, so the set of log keys stays known and bounded.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypedDict, Unpack
from uuid import UUID

from structlog.contextvars import bind_contextvars, bound_contextvars, get_contextvars

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
