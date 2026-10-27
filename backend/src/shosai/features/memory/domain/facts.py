"""A fact Leo remembers about a person, and how it changes (Leo §7.2, ADR 0030, ADR 0071).

A fact is current while it is active and not superseded. A candidate waits for the person
and is never used. Editing a statement never rewrites it: the old fact is closed and points to
its successor, so history stays for "what did you know then". Forgetting ends a fact without
deleting it; a forget or a supersession made by the summary's box can be undone for a day.
Pinning, accepting and editing are the person's confirmation: they refresh the fact's decay
and make it the person's own data (MM-D7).
"""

import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.core.agent_tools.context import Taint

STATEMENT_MAX: Final = 500
# Утверждение из извлечения короче: предложение, а не абзац.
EXTRACTED_MAX: Final = 300
RESTORE_WINDOW: Final = timedelta(hours=24)
_SPACES: Final = re.compile(r"\s+")
_CONTROL: Final = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class FactKind(StrEnum):
    """What a fact is about."""

    PREFERENCE = "preference"
    FACT = "fact"
    RELATIONSHIP = "relationship"
    GOAL = "goal"
    PROCEDURE = "procedure"


class SourceKind(StrEnum):
    """Where a fact came from."""

    USER_STATEMENT = "user_statement"
    MEETING = "meeting"
    TEAM_CHAT = "team_chat"
    SETTINGS = "settings"
    USER_EDIT = "user_edit"
    IMPORTED = "imported"


# Источники, где человек говорит сам: только там бывает явная просьба запомнить.
SPOKEN_SOURCES: Final = frozenset({SourceKind.USER_STATEMENT, SourceKind.TEAM_CHAT})
# Источники, которые и есть действие человека: факт из них подтверждён с записи.
OWN_SOURCES: Final = frozenset({SourceKind.SETTINGS, SourceKind.USER_EDIT})


class FactStatus(StrEnum):
    """Where a fact is in its life."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    FORGOTTEN = "forgotten"


class EndReason(StrEnum):
    """Why a fact ended."""

    FORGOT = "forgot"
    TURNED_DOWN = "turned_down"
    EXPIRED = "expired"
    FORGOT_ALL = "forgot_all"


class Sensitivity(StrEnum):
    """Whether a fact is personal in the sense of special categories of data."""

    NORMAL = "normal"
    SENSITIVE = "sensitive"


class MemoryRule(StrEnum):
    """A rule a change breaks; the value is the API's error code."""

    INVALID = "memory_fact_invalid"
    NOT_CANDIDATE = "memory_fact_not_candidate"
    NOT_CURRENT = "memory_fact_not_found"
    RESTORE_CLOSED = "memory_fact_not_restorable"


class MemoryRuleError(ValueError):
    """A change breaks one of memory's rules; `rule` is the API's code."""

    def __init__(self, rule: MemoryRule) -> None:
        super().__init__(rule.value)
        self.rule = rule


def clean_statement(text: str, limit: int = STATEMENT_MAX) -> str:
    """The statement on one line, without control characters; empty or too long is refused."""
    cleaned = _SPACES.sub(" ", _CONTROL.sub("", text)).strip()
    if not cleaned or len(cleaned) > limit:
        raise MemoryRuleError(MemoryRule.INVALID)
    return cleaned


@dataclass(frozen=True, slots=True)
class Fact:
    """A fact as memory's rules see it."""

    id: UUID
    kind: FactKind
    statement: str
    status: FactStatus
    source: SourceKind
    created_at: datetime
    last_confirmed_at: datetime
    explicit: bool = False
    confirmed: bool = False
    pinned: bool = False
    sensitivity: Sensitivity = Sensitivity.NORMAL
    source_taint: Taint = Taint.NONE
    # Уверенность приёма: 1 — человек подтвердил; меньше — по ответу политики (§6.3).
    confidence: float = 1.0
    confirmations: int = 0
    valid_to: datetime | None = None
    superseded_by: UUID | None = None
    ended_reason: EndReason | None = None
    ended_at: datetime | None = None

    @property
    def current(self) -> bool:
        """Active and not superseded: the fact Leo uses."""
        return self.status is FactStatus.ACTIVE and self.valid_to is None

    @property
    def pending(self) -> bool:
        """A candidate still waiting for the person."""
        return self.status is FactStatus.CANDIDATE and self.valid_to is None


def confirmed_on_write(source: SourceKind, *, explicit: bool) -> bool:
    """Whether a new fact is the person's own data from the start: their edit, their own
    setting, or a statement they asked Leo to remember."""
    return source in OWN_SOURCES or (explicit and source in SPOKEN_SOURCES)


def accept(fact: Fact, now: datetime) -> Fact:
    """The person says Remember: the candidate becomes active and confirmed."""
    if not fact.pending:
        raise MemoryRuleError(MemoryRule.NOT_CANDIDATE)
    return replace(
        fact,
        status=FactStatus.ACTIVE,
        confirmed=True,
        confirmations=fact.confirmations + 1,
        last_confirmed_at=now,
    )


def confirm_again(fact: Fact, now: datetime) -> Fact:
    """The person said it again, or pinned it: its decay starts over."""
    if not fact.current:
        raise MemoryRuleError(MemoryRule.NOT_CURRENT)
    return replace(fact, confirmations=fact.confirmations + 1, last_confirmed_at=now)


def pin(fact: Fact, *, pinned: bool, now: datetime) -> Fact:
    """Pinning a current fact confirms it; unpinning changes only the pin."""
    if not fact.current:
        raise MemoryRuleError(MemoryRule.NOT_CURRENT)
    if not pinned:
        return replace(fact, pinned=False)
    return replace(confirm_again(fact, now), pinned=True, confirmed=True)


def forget(fact: Fact, reason: EndReason, now: datetime) -> Fact:
    """A current fact or a candidate ends; a candidate turned down ends as such."""
    if not (fact.current or fact.pending):
        raise MemoryRuleError(MemoryRule.NOT_CURRENT)
    if fact.pending and reason is EndReason.FORGOT:
        reason = EndReason.TURNED_DOWN
    return replace(
        fact, status=FactStatus.FORGOTTEN, pinned=False, ended_reason=reason, ended_at=now
    )


def supersede(old: Fact, new: Fact, now: datetime) -> tuple[Fact, Fact]:
    """The new statement takes the old one's place: the old is closed and names its successor;
    a pin stays with the fact the person sees."""
    if not (old.current or old.pending):
        raise MemoryRuleError(MemoryRule.NOT_CURRENT)
    if new.id == old.id or new.status is not FactStatus.ACTIVE or new.valid_to is not None:
        raise MemoryRuleError(MemoryRule.INVALID)
    closed = replace(old, valid_to=now, superseded_by=new.id, pinned=False)
    return closed, replace(new, pinned=old.pinned)


def restore(fact: Fact, successor: Fact | None, now: datetime) -> tuple[Fact, Fact | None]:
    """Within a day, a forgotten fact comes back, or a superseded one takes its place again
    and its successor ends."""
    if fact.status is FactStatus.FORGOTTEN and fact.ended_at is not None:
        if now - fact.ended_at > RESTORE_WINDOW or fact.ended_reason is EndReason.EXPIRED:
            raise MemoryRuleError(MemoryRule.RESTORE_CLOSED)
        back = replace(fact, status=FactStatus.ACTIVE, ended_reason=None, ended_at=None)
        return back, None
    if fact.valid_to is None or successor is None or successor.id != fact.superseded_by:
        raise MemoryRuleError(MemoryRule.RESTORE_CLOSED)
    if now - fact.valid_to > RESTORE_WINDOW:
        raise MemoryRuleError(MemoryRule.RESTORE_CLOSED)
    back = replace(fact, valid_to=None, superseded_by=None, pinned=successor.pinned)
    return back, forget(successor, EndReason.FORGOT, now) if successor.current else successor
