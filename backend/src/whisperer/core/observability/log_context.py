"""Context carried by every log line of one unit of work (target architecture §16.2).

The fields live in context variables: each asyncio task sees its own values, and the
values never leak into a concurrent request or the next task a worker takes. Only the
fields of `LogFields` exist, so the set of log keys stays known and bounded.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypedDict, Unpack
from uuid import UUID

from structlog.contextvars import bound_contextvars

from whisperer.core.kernel.homes import Home


class LogFields(TypedDict, total=False):
    """Fields a unit of work may add to its log lines; each is an id, never personal data."""

    request_id: str
    home: Home
    org_id: UUID
    user_id: UUID
    session_id: UUID
    task_name: str
    task_id: str


@contextmanager
def log_context(**fields: Unpack[LogFields]) -> Iterator[None]:
    """Add the fields to every log line written inside the block; restore the outer ones after."""
    with bound_contextvars(**{key: str(value) for key, value in fields.items()}):
        yield
