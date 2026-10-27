"""How long a fact and its traces live (Leo §7.2, ADR 0071 MM-D4, MM-D8).

A fact follows its source. Leaving a workspace hides its facts at once and erases them a week
later unless the membership comes back; a deleted workspace's facts go at once. A meeting's
facts hide with the meeting and are erased when notes purges it. A team chat's facts go with
the chat's disconnection and when their message passes the workspace's retention. A candidate
unanswered for 30 days leaves, except those carried over from the draft, which wait for the
person's review. Ended facts are kept 180 days — for "never ask again" and history — then
purged.
"""

from datetime import datetime, timedelta
from typing import Final

from shosai.features.memory.domain.facts import Fact, FactStatus, SourceKind

DEPARTURE_GRACE: Final = timedelta(days=7)
# Удалённая встреча скрыта семь дней, потом notes её стирает; факты — вместе с ней.
MEETING_PURGE_AFTER: Final = timedelta(days=7)
CANDIDATE_LIFETIME: Final = timedelta(days=30)
ENDED_KEPT: Final = timedelta(days=180)
CHAT_RETENTION_DAYS: Final = frozenset({30, 90, 365})


def erase_after_departure(left_at: datetime) -> datetime:
    """When the facts of a workspace the person left are erased, unless they come back."""
    return left_at + DEPARTURE_GRACE


def erase_after_meeting_deleted(deleted_at: datetime) -> datetime:
    """When the facts of a deleted meeting are erased, unless the meeting is restored."""
    return deleted_at + MEETING_PURGE_AFTER


def past_chat_retention(said_at: datetime, retention_days: int, now: datetime) -> bool:
    """Whether a team chat's fact has passed the retention of the message it came from."""
    if retention_days not in CHAT_RETENTION_DAYS:
        message = f"хранение сообщений чата — {sorted(CHAT_RETENTION_DAYS)} дней"
        raise ValueError(message)
    return now - said_at > timedelta(days=retention_days)


def candidate_expired(fact: Fact, now: datetime) -> bool:
    """A candidate unanswered for 30 days; the draft's carried-over ones never expire."""
    return (
        fact.pending
        and fact.source is not SourceKind.IMPORTED
        and now - fact.created_at > CANDIDATE_LIFETIME
    )


def ended_at(fact: Fact) -> datetime | None:
    """When the fact stopped being current or pending: forgotten, or superseded."""
    if fact.status is FactStatus.FORGOTTEN:
        return fact.ended_at
    return fact.valid_to


def purgeable(fact: Fact, now: datetime) -> bool:
    """An ended fact kept its 180 days."""
    end = ended_at(fact)
    return end is not None and now - end > ENDED_KEPT
