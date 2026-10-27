"""What a message in the summary's "Ask or update" box changes (ADR 0071 MM-D3).

A model reads the person's message with their current facts, each under a short reference,
and answers what to remember, which facts to correct and which to forget, with an answer to
a question if one was asked. Only references the model was given count: a reference it made
up changes nothing. A fact is either corrected or forgotten, never both — forgetting wins,
since it is what the person asked to undo. Each change can be undone for a day.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from shosai.features.memory.domain.facts import (
    EXTRACTED_MAX,
    FactKind,
    MemoryRuleError,
    clean_statement,
)

REMEMBER_MAX: Final = 5
UPDATE_MAX: Final = 10
FORGET_MAX: Final = 10
ANSWER_MAX: Final = 2_000


@dataclass(frozen=True, slots=True)
class NewStatement:
    """A statement the person asks Leo to remember."""

    statement: str
    kind: FactKind


@dataclass(frozen=True, slots=True)
class Correction:
    """A fact the message corrects, and its new statement."""

    fact_id: UUID
    statement: str


@dataclass(frozen=True, slots=True)
class BoxReply:
    """The model's reply as read: references still unresolved."""

    answer: str | None
    remember: Sequence[NewStatement]
    update: Sequence[tuple[str, str]]
    forget: Sequence[str]


@dataclass(frozen=True, slots=True)
class BoxPlan:
    """What the message changes, by fact id, within the box's limits."""

    answer: str | None
    remember: tuple[NewStatement, ...]
    update: tuple[Correction, ...]
    forget: tuple[UUID, ...]

    @property
    def changes(self) -> int:
        """How many facts the message changes."""
        return len(self.remember) + len(self.update) + len(self.forget)


def _statement(text: str) -> str | None:
    try:
        return clean_statement(text, EXTRACTED_MAX)
    except MemoryRuleError:
        return None


def plan(reply: BoxReply, refs: Mapping[str, UUID]) -> BoxPlan:
    """The changes the reply asks for, resolved against the references it was given."""
    forget = tuple(dict.fromkeys(refs[ref] for ref in reply.forget if ref in refs))[:FORGET_MAX]
    gone = set(forget)
    corrections: dict[UUID, str] = {}
    for ref, text in reply.update:
        fact_id = refs.get(ref)
        statement = _statement(text)
        if fact_id is None or fact_id in gone or statement is None:
            continue
        corrections.setdefault(fact_id, statement)
    remember: list[NewStatement] = []
    for item in reply.remember:
        statement = _statement(item.statement)
        if statement is not None and statement not in {kept.statement for kept in remember}:
            remember.append(NewStatement(statement, item.kind))
    answer = (reply.answer or "").strip()[:ANSWER_MAX] or None
    update = tuple(Correction(fact_id, text) for fact_id, text in corrections.items())
    return BoxPlan(answer, tuple(remember[:REMEMBER_MAX]), update[:UPDATE_MAX], forget)
