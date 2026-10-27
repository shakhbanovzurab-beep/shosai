"""`turn.route@1`: which toolsets fill the room the rule leaves (DL-D3, ADR 0069).

The agent's rule keeps the core toolset, the page's and the thread's own whole; then it adds
the others in a fixed order while segment 2's 4 000 tokens hold (ADR 0068 AG-D7). This
policy is asked only when some allowed toolsets do not fit: one `noul` per such candidate
— is any of its tools needed for the latest message — and the candidates it surely needs
come first, by probability; the rest keep the rule's order. It never removes what the rule
keeps, and `load_toolset` still recovers a miss. Skill, tier and "clarify first" come with
studio and the `ask_user` UI (step 14).
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from shosai.core.ai.decisions import NoulQuestion, Question
from shosai.features.decisions.domain.calibration import Aims, CutAim
from shosai.features.decisions.domain.case_fields import records, text, whole
from shosai.features.decisions.domain.policy import Policy, question_text
from shosai.features.decisions.domain.state import Fact, TextField, build_state, clip
from shosai.features.decisions.domain.verdicts import Signal, Verdict

# Leo §6.3: не больше 15 кандидатов в одном запросе.
MAX_CANDIDATES: Final = 15
REQUEST_TOKENS: Final = 600
PREVIOUS_TOKENS: Final = 120
SUMMARY_TOKENS: Final = 80
SECTION_CHARS: Final = 40
NEEDS_PREFIX: Final = "needs_"
TOOLSET_NAME: Final = re.compile(r"[a-z][a-z0-9_]{0,39}")

NEEDS_INSTRUCTIONS: Final = (
    "Decide whether answering the user's latest message needs any of these tools:"
)
NEEDS_TRUE: Final = "At least one of these tools is needed to answer the message well."
NEEDS_FALSE: Final = "The message can be answered well without these tools."


@dataclass(frozen=True, slots=True)
class ToolsetCandidate:
    """An allowed toolset the rule could not fit whole, and what its tools do (English)."""

    name: str
    summary: str

    def __post_init__(self) -> None:
        if not TOOLSET_NAME.fullmatch(self.name):
            message = f"имя набора инструментов: {self.name!r}"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class TurnFacts:
    """A turn's question and the toolsets left to rank, in the rule's order."""

    question: str
    # Начало прошлого ответа: продолжение разговора часто зовёт те же инструменты.
    previous: str
    # Раздел страницы кабинета, если ход задан со страницы.
    section: str
    candidates: tuple[ToolsetCandidate, ...]
    forced: int
    room: int
    turn: int


class TurnRoute(Policy[TurnFacts, tuple[str, ...]]):
    """Version 1: candidates surely needed first, by probability; the rest as the rule puts them."""

    point = "turn.route"
    version = 1
    deadline = timedelta(milliseconds=350)
    cuts = ("needs",)
    # «Нужен» поднимает набор выше правила: его точность и подгоняется; «не уверен» — к
    # порядку правила.
    aims = Aims(
        cuts={"needs": CutAim(Verdict.YES, precision=0.8, unsure_joins=Verdict.NO)},
        margin=0.05,
        accuracy_floor=0.8,
        # Leo §8.2: `load_toolset` нужен не чаще чем в 5 % ходов — нужный набор находится в 95 %.
        careful_floor=0.95,
    )

    def settled(self, facts: TurnFacts, rule: tuple[str, ...]) -> bool:
        """Nothing to rank when every allowed toolset fits."""
        return not facts.candidates

    def questions(self, facts: TurnFacts) -> Mapping[str, Question]:
        """One question per candidate, up to fifteen."""
        return {
            NEEDS_PREFIX + candidate.name: NoulQuestion(
                instructions=f"{NEEDS_INSTRUCTIONS} {clip(candidate.summary, SUMMARY_TOKENS)}",
                when_true=NEEDS_TRUE,
                when_false=NEEDS_FALSE,
            )
            for candidate in facts.candidates[:MAX_CANDIDATES]
        }

    def signals(self, facts: TurnFacts) -> Mapping[str, Signal]:
        """Each candidate's answer through the one cut."""
        return {NEEDS_PREFIX + c.name: Signal("needs") for c in facts.candidates[:MAX_CANDIDATES]}

    def state(self, facts: TurnFacts) -> dict[str, object]:
        """The question, the start of the last answer and the page's section."""
        shown: dict[str, Fact] = {"section": facts.section[:SECTION_CHARS], "turn": facts.turn}
        texts = {
            "request": TextField(facts.question, REQUEST_TOKENS),
            "previous_answer": TextField(facts.previous, PREVIOUS_TOKENS),
        }
        return build_state(shown, texts, self.budget)

    def facts(self, facts: TurnFacts) -> Mapping[str, Fact]:
        """How many candidates, how many kept whole, the room, the turn, whether a page."""
        return {
            "candidates": len(facts.candidates),
            "forced": facts.forced,
            "room": facts.room,
            "turn": facts.turn,
            "page": bool(facts.section),
        }

    def outcome(
        self, facts: TurnFacts, verdicts: Mapping[str, Verdict], chances: Mapping[str, float]
    ) -> tuple[str, ...]:
        """The candidates surely needed, the likeliest first; ties keep the rule's order."""
        needed = [
            (index, candidate.name)
            for index, candidate in enumerate(facts.candidates[:MAX_CANDIDATES])
            if verdicts.get(NEEDS_PREFIX + candidate.name) is Verdict.YES
        ]
        needed.sort(key=lambda item: (-chances.get(NEEDS_PREFIX + item[1], 0.0), item[0]))
        return tuple(name for _, name in needed)

    def careful(self, rule: tuple[str, ...], judged: tuple[str, ...]) -> tuple[str, ...]:
        """The ranking: routing has no careful side, and the rule's own part is never in it."""
        return judged

    def less_careful(self, value: tuple[str, ...], rule: tuple[str, ...]) -> bool:
        """Never: a ranking only orders candidates the rule had left out."""
        return False

    def code(self, value: tuple[str, ...]) -> str:
        """The ranked toolsets, comma-separated; `-` for none."""
        return ",".join(value) or "-"

    def parse_facts(self, raw: Mapping[str, object]) -> TurnFacts:
        """A turn's facts from a dataset case."""
        candidates = tuple(
            ToolsetCandidate(text(item, "name"), text(item, "summary"))
            for item in records(raw, "candidates")
        )
        return TurnFacts(
            question=text(raw, "question"), previous=text(raw, "previous"),
            section=text(raw, "section"), candidates=candidates, forced=whole(raw, "forced"),
            room=whole(raw, "room"), turn=whole(raw, "turn"),
        )  # fmt: skip

    def band(self, outcome: str) -> str:
        """Ranked or not: the names themselves are not a band."""
        return "none" if outcome == "-" else "ranked"

    def confirms(self, outcome: str, observation: Mapping[str, object] | None) -> bool:
        """The run called a toolset the ranking brought in."""
        called = observation.get("called") if observation is not None else None
        ranked = set() if outcome == "-" else set(outcome.split(","))
        return isinstance(called, list) and bool(ranked.intersection(map(str, called)))

    def careful_case(self, expected: tuple[str, ...]) -> bool:
        """A turn that needs at least one candidate."""
        return bool(expected)

    def agrees(self, judged: tuple[str, ...], expected: tuple[str, ...]) -> bool:
        """Every needed candidate ranked, and nothing that is not needed; order aside."""
        return set(judged) == set(expected)

    def wording(self) -> Mapping[str, object]:
        """The question's fixed words; each candidate's summary is its tools' registered text."""
        template = NoulQuestion(NEEDS_INSTRUCTIONS, when_true=NEEDS_TRUE, when_false=NEEDS_FALSE)
        return {"needs": question_text(template)}


TURN_ROUTE: Final = TurnRoute()
