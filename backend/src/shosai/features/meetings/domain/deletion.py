"""A meeting's deletion (MT-D8, as files' FL-D5): hidden for 7 days, then gone for good.

The owner deletes their meeting, never while it is live: it leaves every list, read,
search, Leo, workspace and share link at once, and its minutes stay counted. Within the 7
days support may bring it back, shared nowhere; after them the purge removes it with its
transient objects and billing keeps its minutes as a tombstone.
"""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

HIDDEN_FOR: Final = timedelta(days=7)


class DeletionRule(StrEnum):
    """Why a person may not delete a meeting; the value is the API's error code."""

    NOT_OWNER = "meeting_not_yours"
    LIVE = "meeting_active"


def deletion_refusal(*, owner: bool, live: bool) -> DeletionRule | None:
    """Why the person may not delete the meeting now, or None when they may."""
    if not owner:
        return DeletionRule.NOT_OWNER
    if live:
        return DeletionRule.LIVE
    return None


def purge_after(now: datetime) -> datetime:
    """Meetings deleted at or before this moment are due for the purge."""
    return now - HIDDEN_FOR


def restorable(deleted_at: datetime | None, now: datetime) -> bool:
    """Whether a deleted meeting is still within its 7 hidden days."""
    return deleted_at is not None and deleted_at > purge_after(now)
