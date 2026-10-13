"""Identifiers the platform creates: UUIDv7 (target architecture §8.2).

A UUIDv7 starts with its creation time in milliseconds, so new keys land at the right edge
of a B-tree index and sort by creation time across processes. Records, events, tasks and
requests take their ids from here.
"""

import uuid
from uuid import UUID


def new_id() -> UUID:
    """A new time-ordered identifier (UUIDv7)."""
    return uuid.uuid7()
