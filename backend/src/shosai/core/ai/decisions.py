"""Typed questions to a decision model and its answers (Leo architecture §6.1, ADR 0026).

The shape is OpenRouter's Decisions API (`/api/alpha/decisions`, read on 2026-10-13): a
state and named questions. A `choice` picks one of its options, a `score` places the state
on an ordered scale, a `noul` gives the probability that its proposition is true. Each
question's instructions and criteria are model-facing English text the caller owns and
registers. Value types only, no client or framework.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from shosai.core.ai.calls import ModelRef
from shosai.core.ai.results import Usage

QUESTION_NAME_MAX: Final = 64
CHOICE_OPTIONS_MAX: Final = 255
SCORE_LEVELS: Final = range(2, 11)


@dataclass(frozen=True, slots=True)
class ChoiceQuestion:
    """Pick one option; `criteria` describes each option by its name."""

    instructions: str
    criteria: Mapping[str, str]

    def __post_init__(self) -> None:
        if not 2 <= len(self.criteria) <= CHOICE_OPTIONS_MAX:
            message = f"выбор — от 2 до {CHOICE_OPTIONS_MAX} вариантов"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class ScoreQuestion:
    """Place the state on a scale; `criteria` describes each level, the lowest first."""

    instructions: str
    criteria: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.criteria) not in SCORE_LEVELS:
            message = "шкала — от 2 до 10 уровней"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class NoulQuestion:
    """The probability that a proposition is true; criteria describe both sides, if given."""

    instructions: str
    when_true: str | None = None
    when_false: str | None = None

    def __post_init__(self) -> None:
        if (self.when_true is None) != (self.when_false is None):
            message = "критерии вероятности — обе стороны или ни одной"
            raise ValueError(message)


type Question = ChoiceQuestion | ScoreQuestion | NoulQuestion


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    """A state and the questions asked about it, in one round trip."""

    state: str | Mapping[str, Any]
    questions: Mapping[str, Question] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.questions:
            message = "решению нужен хотя бы один вопрос"
            raise ValueError(message)
        for name, question in self.questions.items():
            if not 1 <= len(name) <= QUESTION_NAME_MAX or not question.instructions.strip():
                message = "у вопроса — имя до 64 символов и инструкция"
                raise ValueError(message)


@dataclass(frozen=True, slots=True)
class ChoiceAnswer:
    """The option picked, with the model's confidence and each option's probability."""

    choice: str
    confidence: float | None
    probabilities: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class ScoreAnswer:
    """The expected level on the scale (0 is the lowest), with the probability of each level."""

    score: float
    confidence: float | None
    probabilities: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class NoulAnswer:
    """The probability that the proposition is true."""

    probability: float


type Answer = ChoiceAnswer | ScoreAnswer | NoulAnswer


@dataclass(frozen=True, slots=True)
class Decision:
    """Every question's answer, the dated model snapshot that gave them, and the usage."""

    answers: Mapping[str, Answer]
    model: ModelRef
    snapshot: str
    decision_id: str | None
    usage: Usage
