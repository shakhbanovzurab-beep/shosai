"""What agent and memory ask of each other (memory plan §3.2, ADR 0071).

`memory` binds the two ports a turn reads: the profile core of segment 4 (`ProfileFacts`),
read in the context's own transaction, and the facts recalled for the question of segment 7
(`MemoryRecall`), started beside it with a deadline. Each fact says what it raises the run's
taint to: a fact the person confirmed is their own data and raises nothing; any other keeps
its source's taint, at least external (MM-D7). Agent binds `PersonWords`: the person's own
words of a finished turn, which memory admits facts from, never tool rounds or attachments.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import PortKey

__all__ = [
    "MEMORY_RECALL",
    "PERSON_WORDS",
    "PROFILE_FACTS",
    "MemoryRecall",
    "PersonWords",
    "PriorExchange",
    "ProfileCore",
    "ProfileFacts",
    "RecallRequest",
    "RecalledFact",
    "TurnWords",
]


@dataclass(frozen=True, slots=True)
class RecalledFact:
    """A fact for the model: the statement, its kind, the label it is wrapped with and the
    taint it raises the run to (`NONE` for a fact the person confirmed)."""

    statement: str
    kind: str
    label: Provenance
    taint: Taint


@dataclass(frozen=True, slots=True)
class RecallRequest:
    """What a turn asks memory to recall: the person, their question and its context, the
    workspaces they are a member of now, their consent and the budget."""

    home: Home
    user_id: UUID
    query: str
    spaces: frozenset[UUID]
    # Без согласия на трансграничную передачу вопрос не уходит в модель эмбеддингов (nfr-14).
    cross_border_consent: bool
    max_tokens: int
    deadline: timedelta


class MemoryRecall(Protocol):
    """Recalls what Leo remembers about the person for a turn (memory)."""

    async def recall(self, request: RecallRequest) -> tuple[RecalledFact, ...]:
        """The facts that matter for the query within the budget; empty when memory is off,
        when there is nothing, or when the deadline passed."""
        ...


@dataclass(frozen=True, slots=True)
class ProfileCore:
    """Segment 4's part from memory: whether memory is on, and the pinned facts and the
    person's preferences in a fixed order, so the block stays the same between turns."""

    enabled: bool
    facts: tuple[RecalledFact, ...]


class ProfileFacts(Protocol):
    """The person's profile core for the context (memory)."""

    async def profile(
        self, session: AsyncSession, user_id: UUID, spaces: frozenset[UUID], max_tokens: int
    ) -> ProfileCore:
        """Read in the caller's transaction, as the person; within the budget."""
        ...


@dataclass(frozen=True, slots=True)
class PriorExchange:
    """An exchange before the turn, for references only: the question and the answer's
    opening."""

    question: str
    answer_head: str


@dataclass(frozen=True, slots=True)
class TurnWords:
    """The person's own words of a finished turn, where they were said and what the run saw."""

    thread_id: UUID
    message_id: UUID
    # Пространство треда: факт из него живёт, пока человек в пространстве (MM-D4).
    org_id: UUID | None
    text: str
    # Итоговое заражение хода: подозрительный ход память пропускает (Leo §7.4).
    taint: Taint
    said_at: datetime
    before: tuple[PriorExchange, ...]


class PersonWords(Protocol):
    """The person's words of a turn, for memory's admission (agent)."""

    async def of_turn(self, session: AsyncSession, user_id: UUID, run_id: UUID) -> TurnWords | None:
        """The turn's question as the person wrote or said it; None for a turn that is not a
        person's answered question (the operator's, a failed or deleted one)."""
        ...


MEMORY_RECALL: Final = PortKey[MemoryRecall]("agent.memory_recall")
PROFILE_FACTS: Final = PortKey[ProfileFacts]("agent.profile_facts")
PERSON_WORDS: Final = PortKey[PersonWords]("agent.person_words")
