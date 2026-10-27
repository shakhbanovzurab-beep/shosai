"""Small parts of a turn's context: a segment's cap, the person's zone, the run's person."""

from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.budgets import SEGMENT_CAPS, Segment

UTC_ZONE: Final = "UTC"


def cap(segment: int) -> int:
    """A segment's cap in tokens, by its number in Leo §7.3."""
    return SEGMENT_CAPS[list(Segment)[segment - 1]]


def zone_info(zone: str) -> ZoneInfo:
    """The zone the person's profile names, UTC for one the system does not know."""
    try:
        return ZoneInfo(zone)
    except ZoneInfoNotFoundError, ValueError:
        return ZoneInfo(UTC_ZONE)


def person_of(payload: TurnPayload) -> UUID:
    """The person a run acts for."""
    if payload.user_id is None:
        message = "ход Leo идёт от имени человека"
        raise ValueError(message)
    return payload.user_id
