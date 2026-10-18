"""The storage quota: reservations, the 90 days over the limit and the 7 days hidden.

Usage is what an owner's files hold plus what pending uploads reserve; a reservation never
lets it pass the limit (None: unlimited). Over the limit after a downgrade, a lapse or a
restore, nothing goes for 90 days, with reminders 30, 7 and 1 day before the end; then the
newest files go until usage fits (FL-D2). A deleted file is hidden for 7 days, out of the
quota, then gone (FL-D5).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

GIB: Final = 1024**3
OVER_LIMIT_WINDOW: Final = timedelta(days=90)
REMINDERS_BEFORE: Final = (timedelta(days=30), timedelta(days=7), timedelta(days=1))
HIDDEN_FOR: Final = timedelta(days=7)


class QuotaExceededError(ValueError):
    """The bytes do not fit the owner's limit."""


@dataclass(frozen=True, slots=True)
class Usage:
    """An owner's stored and reserved bytes."""

    used: int
    reserved: int

    def __post_init__(self) -> None:
        if self.used < 0 or self.reserved < 0:
            message = "занятое и зарезервированное место не отрицательны"
            raise ValueError(message)

    @property
    def total(self) -> int:
        """What counts against the limit."""
        return self.used + self.reserved


def limit_bytes(file_manager_gb: int | None) -> int | None:
    """The plan's storage in bytes; None is unlimited."""
    return None if file_manager_gb is None else file_manager_gb * GIB


def reserve(usage: Usage, limit: int | None, size: int) -> Usage:
    """Reserve an upload's bytes, or refuse when they would pass the limit."""
    if limit is not None and usage.total + size > limit:
        raise QuotaExceededError
    return Usage(usage.used, usage.reserved + size)


def settle(usage: Usage, size: int) -> Usage:
    """A reserved upload became a file: its bytes move from reserved to used."""
    return Usage(usage.used + size, max(usage.reserved - size, 0))


def release(usage: Usage, size: int) -> Usage:
    """A reservation ended without a file: its bytes are free again."""
    return Usage(usage.used, max(usage.reserved - size, 0))


def free(usage: Usage, size: int) -> Usage:
    """A file left the quota (hidden or transferred): its bytes are free again."""
    return Usage(max(usage.used - size, 0), usage.reserved)


def over_limit(usage: Usage, limit: int | None) -> bool:
    """Whether the owner holds more than the plan allows."""
    return limit is not None and usage.used > limit


def reminder_due(since: datetime, now: datetime, sent: int) -> int | None:
    """The index of the next reminder to send now, or None (each goes once, in order)."""
    if sent >= len(REMINDERS_BEFORE):
        return None
    end = since + OVER_LIMIT_WINDOW
    return sent if now >= end - REMINDERS_BEFORE[sent] else None


def removal_due(since: datetime, now: datetime) -> bool:
    """Whether the 90 days are over."""
    return now >= since + OVER_LIMIT_WINDOW


@dataclass(frozen=True, slots=True)
class StoredFile:
    """A file as the quota sees it."""

    file_id: UUID
    size_bytes: int
    created_at: datetime


def newest_over_limit(files: Sequence[StoredFile], used: int, limit: int) -> list[UUID]:
    """The newest files to remove until what stays fits the limit."""
    chosen: list[UUID] = []
    for item in sorted(files, key=lambda f: (f.created_at, f.file_id), reverse=True):
        if used <= limit:
            break
        chosen.append(item.file_id)
        used -= item.size_bytes
    return chosen


def purge_due(deleted_at: datetime, now: datetime) -> bool:
    """Whether a hidden file's 7 days are over."""
    return now >= deleted_at + HIDDEN_FOR


class QuotaAction(StrEnum):
    """What the quota does for an owner now; the value is the metric's label."""

    MARK = "marked"
    CLEAR = "cleared"
    REMIND = "reminded"
    REMOVE = "removed"


@dataclass(frozen=True, slots=True)
class OverLimitMark:
    """An owner's time over the limit: since when, and how many reminders went."""

    since: datetime | None
    reminders_sent: int


def quota_action(
    usage: Usage, limit: int | None, mark: OverLimitMark, now: datetime
) -> QuotaAction | None:
    """The one step FL-D2 takes for the owner now, or None when nothing is due."""
    if not over_limit(usage, limit):
        return QuotaAction.CLEAR if mark.since is not None else None
    if mark.since is None:
        return QuotaAction.MARK
    if removal_due(mark.since, now):
        return QuotaAction.REMOVE
    if reminder_due(mark.since, now, mark.reminders_sent) is not None:
        return QuotaAction.REMIND
    return None


def removal_date(since: datetime) -> datetime:
    """When the files over the limit go, for the reminders and the banner."""
    return since + OVER_LIMIT_WINDOW
