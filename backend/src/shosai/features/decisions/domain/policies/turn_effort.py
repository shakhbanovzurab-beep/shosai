"""`turn.effort@1`: whether a turn's question needs careful, several-step reasoning (agent step
21; the owner's choice of 2026-10-27 — ChatGPT's "Auto").

The standard tier answers at its rule's effort, `low`: a greeting, a thank-you or a one-step
request starts at once. This policy reads the person's latest message, the start of the last
answer, the page it was asked from and whether files came with it, and asks one `noul`: does
answering it well need careful reasoning — analysing, planning, comparing, calculating,
writing or restructuring something substantial, or doing several things at once? Only a sure
yes raises the turn to `deep`; an unsure answer stays at the rule, and nothing lowers it.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from typing import Final

from shosai.core.ai.decisions import NoulQuestion, Question
from shosai.features.decisions.domain.calibration import Aims, CutAim
from shosai.features.decisions.domain.case_fields import text, whole
from shosai.features.decisions.domain.policy import Policy, question_text
from shosai.features.decisions.domain.state import Fact, TextField, build_state
from shosai.features.decisions.domain.verdicts import Signal, Verdict

DELIBERATE: Final = "deliberate"
QUESTION_TOKENS: Final = 600
PREVIOUS_TOKENS: Final = 120
SECTION_CHARS: Final = 40

DELIBERATE_QUESTION: Final = NoulQuestion(
    instructions=(
        "Decide whether answering the user's latest message well needs careful, several-step "
        "reasoning before replying."
    ),
    when_true=(
        "The message asks to analyse, plan, compare options, calculate, reason through a "
        "problem, write or restructure something substantial, or do several things at once."
    ),
    when_false=(
        "The message is a greeting, thanks, small talk or a confirmation, a simple question "
        "with a short factual answer, or one simple action such as finding, showing, "
        "creating, moving or renaming one thing."
    ),
)


class TurnEffort(IntEnum):
    """How hard the turn's model reasons; a higher value is more careful."""

    STANDARD = 0
    DEEP = 1


@dataclass(frozen=True, slots=True)
class EffortFacts:
    """A turn's question and what surrounds it."""

    question: str
    # Начало прошлого ответа: «а второе?» понятно только рядом с ним.
    previous: str
    # Раздел страницы кабинета, если ход задан со страницы.
    section: str
    files: int
    turn: int


class TurnEffortPolicy(Policy[EffortFacts, TurnEffort]):
    """Version 1: deep only when the question surely needs careful reasoning."""

    point = "turn.effort"
    version = 1
    # Ответ нужен, пока читается контекст хода (около 0,9 с): дольше ход ждать не станет.
    deadline = timedelta(milliseconds=450)
    cuts = (DELIBERATE,)
    # «Глубоко» поднимает уровень выше правила: подгоняется его точность; «не уверен» — правило.
    aims = Aims(
        cuts={DELIBERATE: CutAim(Verdict.YES, precision=0.85, unsure_joins=Verdict.NO)},
        margin=0.05,
        accuracy_floor=0.85,
        careful_floor=0.8,
    )

    def settled(self, facts: EffortFacts, rule: TurnEffort) -> bool:
        """Nothing to judge without a question, or when the rule already reasons deeply."""
        return not facts.question.strip() or rule is TurnEffort.DEEP

    def questions(self, facts: EffortFacts) -> Mapping[str, Question]:
        """Whether the question needs careful reasoning."""
        return {DELIBERATE: DELIBERATE_QUESTION}

    def signals(self, facts: EffortFacts) -> Mapping[str, Signal]:
        """The probability as is."""
        return {DELIBERATE: Signal(DELIBERATE)}

    def state(self, facts: EffortFacts) -> dict[str, object]:
        """The question, the start of the last answer, the page's section and the files."""
        shown: dict[str, Fact] = {
            "section": facts.section[:SECTION_CHARS], "files": facts.files, "turn": facts.turn,
        }  # fmt: skip
        texts = {
            "request": TextField(facts.question, QUESTION_TOKENS),
            "previous_answer": TextField(facts.previous, PREVIOUS_TOKENS),
        }
        return build_state(shown, texts, self.budget)

    def facts(self, facts: EffortFacts) -> Mapping[str, Fact]:
        """How long the question was, the files, the turn, whether a page: never its words."""
        return {
            "question_words": len(facts.question.split()),
            "files": facts.files,
            "turn": facts.turn,
            "page": bool(facts.section),
        }

    def outcome(
        self, facts: EffortFacts, verdicts: Mapping[str, Verdict], chances: Mapping[str, float]
    ) -> TurnEffort:
        """Deep only for a sure yes."""
        if verdicts.get(DELIBERATE, Verdict.UNSURE) is Verdict.YES:
            return TurnEffort.DEEP
        return TurnEffort.STANDARD

    def careful(self, rule: TurnEffort, judged: TurnEffort) -> TurnEffort:
        """The deeper of the two: a judgement only raises the rule's effort."""
        return max(rule, judged)

    def less_careful(self, value: TurnEffort, rule: TurnEffort) -> bool:
        """An effort below the rule's."""
        return value < rule

    def code(self, value: TurnEffort) -> str:
        """`standard` or `deep`."""
        return value.name.lower()

    def parse_facts(self, raw: Mapping[str, object]) -> EffortFacts:
        """A turn's facts from a dataset case."""
        return EffortFacts(
            question=text(raw, "question"), previous=text(raw, "previous"),
            section=text(raw, "section"), files=whole(raw, "files"), turn=whole(raw, "turn"),
        )  # fmt: skip

    def careful_case(self, expected: TurnEffort) -> bool:
        """A question that needs careful reasoning."""
        return expected is TurnEffort.DEEP

    def wording(self) -> Mapping[str, object]:
        """The one question."""
        return {DELIBERATE: question_text(DELIBERATE_QUESTION)}


TURN_EFFORT: Final = TurnEffortPolicy()
