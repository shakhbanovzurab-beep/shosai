"""What a meeting produced, each with its evidence (plan §3.4 flow 6).

Findings are extracted from the transcript, independent of the write-up's template, so a
rewrite with another template keeps them and their ids (the draft lost the action items'
ticks on every regeneration). Each finding has a kind, a short text, a topic for the map,
an owner and a due date where it has them, and the moment that proves it: an offset span
inside the meeting and a short quote. A finding without text or with evidence outside the
meeting is dropped; a due date before the meeting's day or more than a year after it is
not kept.
"""

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Final

from shosai.features.notes.domain.templates import SectionKind

TEXT_MAX: Final = 500
TOPIC_MAX: Final = 80
QUOTE_MAX: Final = 300
OWNER_MAX: Final = 120
DUE_HORIZON: Final = timedelta(days=366)


class FindingKind(StrEnum):
    """What a finding is."""

    KEY_POINT = "key_point"
    DECISION = "decision"
    ACTION_ITEM = "action_item"
    PROMISE = "promise"
    RISK = "risk"
    QUESTION = "question"


# Какие находки показывает секция записи; в кратком изложении — текст, не находки.
SECTION_FINDINGS: Final = {
    SectionKind.KEY_POINTS: FindingKind.KEY_POINT,
    SectionKind.DECISIONS: FindingKind.DECISION,
    SectionKind.ACTION_ITEMS: FindingKind.ACTION_ITEM,
}


@dataclass(frozen=True, slots=True)
class Evidence:
    """The moment that proves a finding: its span from the meeting's start and a quote."""

    start_ms: int
    end_ms: int
    quote: str


@dataclass(frozen=True, slots=True)
class Finding:
    """One finding as kept."""

    kind: FindingKind
    text: str
    evidence: Evidence
    topic: str | None = None
    owner_speaker: int | None = None
    owner_name: str | None = None
    due_on: date | None = None


@dataclass(frozen=True, slots=True)
class RawFinding:
    """A finding as a model wrote it, before the rules."""

    kind: FindingKind
    text: str
    start_ms: int
    end_ms: int
    quote: str = ""
    topic: str | None = None
    owner_speaker: int | None = None
    owner_name: str | None = None
    due_on: str | None = None


def _clean(raw: str | None, limit: int) -> str | None:
    if raw is None:
        return None
    text = " ".join("".join(c for c in raw if unicodedata.category(c) != "Cc").split())
    return text[:limit] or None


def checked_due(raw: str | None, meeting_started_at: datetime) -> date | None:
    """An ISO date from the meeting's day up to a year after it, else None."""
    if not raw:
        return None
    try:
        due = date.fromisoformat(raw.strip())
    except ValueError:
        return None
    day = meeting_started_at.date()
    return due if day <= due <= day + DUE_HORIZON else None


def checked_finding(
    raw: RawFinding, *, meeting_ms: int, meeting_started_at: datetime
) -> Finding | None:
    """The finding as kept, or None when it has no text or no evidence inside the meeting."""
    text = _clean(raw.text, TEXT_MAX)
    inside = 0 <= raw.start_ms <= raw.end_ms <= meeting_ms
    if text is None or not inside:
        return None
    owner = raw.owner_speaker if raw.owner_speaker is None or raw.owner_speaker >= 0 else None
    return Finding(
        kind=raw.kind,
        text=text,
        evidence=Evidence(raw.start_ms, raw.end_ms, _clean(raw.quote, QUOTE_MAX) or ""),
        topic=_clean(raw.topic, TOPIC_MAX),
        owner_speaker=owner,
        owner_name=_clean(raw.owner_name, OWNER_MAX),
        due_on=checked_due(raw.due_on, meeting_started_at),
    )
