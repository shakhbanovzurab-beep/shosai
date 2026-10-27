"""What becomes of a statement extracted from a turn or a meeting (Leo §6.3, §7.2, ADR 0071).

Similarity tells the subject, not the meaning (measured on `google/gemini-embedding-2`, plan
§1.4): two different facts of a person never come closer than 0.87, while a rewording and a
contradiction of the same fact ("lives in Moscow" and "lives in Berlin") both do, up to 0.98.
So only the same words after normalization confirm a fact the person holds; a statement on
the subject of a current fact proposes to replace it, and the person — or the policy — says
whether it does. A statement on the subject of one the person forgot or turned down is never
asked again unless they ask for it now; one on the subject of a waiting candidate is not asked
twice. Then, until the Decision Layer's `memory.admit` acts (MM-D1), the rule: what the person
asked Leo to remember is saved as theirs, anything else waits as a candidate, at most three
new ones a day. Once the policy acts, a confident statement that is not sensitive is saved
without asking — except one in twenty, still asked so the policy stays measured — and
sensitive or doubtful ones wait. A meeting's statement always waits (MM-D5).
"""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.features.memory.domain.facts import (
    SPOKEN_SOURCES,
    EndReason,
    Fact,
    FactKind,
    FactStatus,
    MemorySource,
)

# Ближе этого два разных факта не подходят ни на одном из 16 языков (замер, план §1.4).
SAME_SUBJECT: Final = 0.87
CANDIDATES_PER_DAY: Final = 3
NEIGHBOURS: Final = 5
STATEMENTS_PER_TURN: Final = 3
STATEMENTS_PER_MEETING: Final = 5
PROBE_EVERY: Final = 20
# Сколько помнится, что человек отказался: столько же, сколько хранится конец факта.
REFUSALS_REMEMBERED: Final = timedelta(days=180)
# Причины конца, после которых то же самое больше не спрашивают; угасший факт можно выучить снова.
REFUSALS: Final = frozenset({EndReason.FORGOT, EndReason.TURNED_DOWN, EndReason.FORGOT_ALL})


@dataclass(frozen=True, slots=True)
class Statement:
    """A statement the extractor found, in the person's language."""

    text: str
    kind: FactKind
    explicit: bool
    sensitive: bool
    about_person: bool


@dataclass(frozen=True, slots=True)
class Neighbour:
    """One of the person's facts near the statement, by cosine similarity."""

    fact: Fact
    similarity: float


class Judgement(StrEnum):
    """What the active `memory.admit` policy says of a statement."""

    STORE = "store"
    ASK = "ask"
    SUPERSEDE = "supersede"
    SKIP = "skip"


class Admission(StrEnum):
    """What memory does with a statement; the value is the metric's outcome."""

    ACTIVE = "active"
    AUTO_SAVED = "auto_saved"
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    SKIPPED_FORGOTTEN = "skipped_forgotten"
    SKIPPED_PENDING = "skipped_pending"
    SKIPPED_CAP = "skipped_cap"
    SKIPPED_JUDGE = "skipped_judge"


@dataclass(frozen=True, slots=True)
class Admit:
    """The admission and the neighbour it concerns: the fact confirmed, the one a saved fact
    supersedes (`supersedes`), or the one a candidate proposes to replace."""

    admission: Admission
    neighbour: UUID | None = None
    supersedes: bool = False

    @property
    def writes(self) -> bool:
        """Whether a new fact is written."""
        return self.admission in {Admission.ACTIVE, Admission.AUTO_SAVED, Admission.CANDIDATE}

    @property
    def confirmed(self) -> bool:
        """Whether the new fact is the person's own from the start."""
        return self.admission is Admission.ACTIVE


def is_probe(statement_id: UUID) -> bool:
    """One statement in twenty, chosen by its id, is asked even when the policy would save it."""
    return statement_id.int % PROBE_EVERY == 0


def explicit_request(statement: Statement, source: MemorySource) -> bool:
    """The person asked Leo to remember it, in their own words."""
    return statement.explicit and source in SPOKEN_SOURCES


def same_words(first: str, second: str) -> bool:
    """The same statement once case, punctuation and spacing are set aside, in any script."""
    return _words(first) == _words(second)


def _words(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    kept = (" " if unicodedata.category(char)[0] in "PZC" else char for char in folded)
    return " ".join("".join(kept).split())


def on_subject(neighbours: Sequence[Neighbour]) -> list[Neighbour]:
    """The neighbours on the statement's subject, the nearest first."""
    close = (item for item in neighbours if item.similarity >= SAME_SUBJECT)
    return sorted(close, key=lambda item: -item.similarity)


def before_judge(
    statement: Statement, source: MemorySource, neighbours: Sequence[Neighbour], now: datetime
) -> Admit | None:
    """A confirmation or a skip decided by the nearest facts alone, or None to go on."""
    for item in on_subject(neighbours):
        fact = item.fact
        if fact.current and same_words(fact.statement, statement.text):
            return Admit(Admission.CONFIRMED, fact.id)
        if fact.pending:
            return Admit(Admission.SKIPPED_PENDING, fact.id)
        if refused(fact, now) and not explicit_request(statement, source):
            return Admit(Admission.SKIPPED_FORGOTTEN, fact.id)
    return None


def subject_fact(neighbours: Sequence[Neighbour]) -> UUID | None:
    """The current fact the statement may replace: the nearest one on its subject."""
    return next((item.fact.id for item in on_subject(neighbours) if item.fact.current), None)


def refused(fact: Fact, now: datetime) -> bool:
    """The person forgot or turned the fact down within the time that is remembered."""
    return (
        fact.status is FactStatus.FORGOTTEN
        and fact.ended_reason in REFUSALS
        and fact.ended_at is not None
        and now - fact.ended_at <= REFUSALS_REMEMBERED
    )


def ask(candidates_today: int, replaces: UUID | None = None) -> Admit:
    """A candidate, unless the day's three are already asked."""
    if candidates_today >= CANDIDATES_PER_DAY:
        return Admit(Admission.SKIPPED_CAP)
    return Admit(Admission.CANDIDATE, replaces)


def by_rule(
    statement: Statement, source: MemorySource, candidates_today: int, subject: UUID | None = None
) -> Admit:
    """Before the policy acts: an explicit request is saved beside what it may change; anything
    else is asked, proposing to replace the current fact on its subject."""
    if explicit_request(statement, source):
        return Admit(Admission.ACTIVE)
    return ask(candidates_today, subject)


@dataclass(frozen=True, slots=True)
class PolicyAnswer:
    """The active policy's judgement, the neighbour a supersession names, and whether the
    statement is one of the probes still asked."""

    judgement: Judgement
    replaces: UUID | None
    probe: bool


def by_policy(
    statement: Statement, source: MemorySource, answer: PolicyAnswer, candidates_today: int
) -> Admit:
    """Once the policy acts: never less careful than the rule (Leo §6.2's monotonic safety)
    for anything the person did not ask for."""
    superseding = answer.judgement is Judgement.SUPERSEDE and answer.replaces is not None
    replaces = answer.replaces if superseding else None
    if explicit_request(statement, source):
        return Admit(Admission.ACTIVE, replaces, supersedes=superseding)
    if answer.judgement is Judgement.SKIP:
        return Admit(Admission.SKIPPED_JUDGE)
    confident = answer.judgement in {Judgement.STORE, Judgement.SUPERSEDE}
    if confident and source in SPOKEN_SOURCES and not statement.sensitive and not answer.probe:
        return Admit(Admission.AUTO_SAVED, replaces, supersedes=superseding)
    return ask(candidates_today, replaces)
