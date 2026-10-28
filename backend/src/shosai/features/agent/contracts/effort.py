"""How hard a turn's model reasons, judged beside the rule (decisions' `turn.effort`; agent step
21, the owner's choice of 2026-10-27).

The standard tier reasons at its rule's effort; a bound judge may find that a question needs
careful, several-step reasoning, and only then does the turn reason more. Without one bound,
every turn keeps its tier's effort.
"""

from dataclasses import dataclass
from typing import Final, Protocol
from uuid import UUID

from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.keys import PortKey


@dataclass(frozen=True, slots=True)
class EffortRequest:
    """What a judge of a turn's effort reads: the person's question, the start of the last
    answer, the page's section, how many files came with it, how many turns the thread had,
    and whom the judgement is for."""

    question: str
    previous: str
    section: str
    files: int
    turn: int
    language: str
    scope: TenancyScope
    cross_border_consent: bool
    run_id: UUID


class EffortJudge(Protocol):
    """Judges whether a turn's question needs careful, several-step reasoning."""

    async def deep(self, request: EffortRequest) -> bool | None:
        """True only when an active version surely found careful reasoning needed; None when
        the judge cannot say, so the turn keeps its tier's effort."""
        ...


TURN_EFFORT_JUDGE: Final = PortKey[EffortJudge]("agent.turn_effort_judge")
