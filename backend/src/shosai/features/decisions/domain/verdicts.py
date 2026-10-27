"""From Jev's answers to verdicts: a probability per signal, read through a cut with a margin.

Jev is calibrated in aggregate but not deterministic (Leo §6.1): the same state may answer
0.79 and then 0.84. So no exact value decides; each signal's probability is compared with
its cut, and a probability inside the cut's unsure band is `UNSURE`, which each policy reads
as its careful side (ADR 0026 point 5).

A signal names the cut it is read through and how its probability comes out of an answer:
a `noul` gives it directly, a `choice` by one option, a `score` as the chance the level is at
least the one named.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from shosai.core.ai.decisions import Answer, ChoiceAnswer, NoulAnswer, ScoreAnswer

MAX_MARGIN = 0.5


class Verdict(StrEnum):
    """What a signal says once read through its cut."""

    YES = "yes"
    NO = "no"
    UNSURE = "unsure"


@dataclass(frozen=True, slots=True)
class Cut:
    """The edges of the unsure band: below `lower` is NO, from `upper` YES, between unsure.

    Edges, not a threshold and a margin: a fitted edge is kept exactly as fitted, with no
    arithmetic that could move a case across it.
    """

    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not 0 <= self.lower <= self.upper <= 1 or self.upper - self.lower > 2 * MAX_MARGIN:
            message = "порог: края от 0 до 1, нижний не выше верхнего, полоса не шире 1"
            raise ValueError(message)

    def verdict(self, probability: float) -> Verdict:
        """YES from the upper edge, NO below the lower one, UNSURE between them."""
        if probability >= self.upper:
            return Verdict.YES
        if probability < self.lower:
            return Verdict.NO
        return Verdict.UNSURE


@dataclass(frozen=True, slots=True)
class Signal:
    """The cut a question's answer is read through, and how its probability is taken."""

    cut: str
    # Для choice — вероятность этого варианта; для score — вероятность уровня не ниже этого.
    option: str | None = None
    at_least: int | None = None


def probability(answer: Answer, signal: Signal) -> float:
    """The signal's probability in the answer."""
    if isinstance(answer, NoulAnswer):
        return answer.probability
    if isinstance(answer, ChoiceAnswer):
        if signal.option is None:
            message = "сигналу выбора нужен вариант"
            raise ValueError(message)
        fallback = 1.0 if answer.choice == signal.option else 0.0
        return answer.probabilities.get(signal.option, fallback)
    return level_at_least(answer, signal)


def level_at_least(answer: ScoreAnswer, signal: Signal) -> float:
    """The chance the level is at least the signal's, from the levels' probabilities."""
    if signal.at_least is None:
        message = "сигналу шкалы нужен уровень"
        raise ValueError(message)
    if not answer.probabilities:
        return 1.0 if answer.score >= signal.at_least else 0.0
    mass = sum(p for level, p in answer.probabilities.items() if int(level) >= signal.at_least)
    return min(mass, 1.0)


def read(
    answers: Mapping[str, Answer], signals: Mapping[str, Signal], cuts: Mapping[str, Cut]
) -> tuple[dict[str, Verdict], dict[str, float]]:
    """Every question's verdict and probability; a question without an answer is unsure."""
    verdicts: dict[str, Verdict] = {}
    chances: dict[str, float] = {}
    for name, signal in signals.items():
        answer = answers.get(name)
        if answer is None:
            verdicts[name] = Verdict.UNSURE
            continue
        chance = probability(answer, signal)
        chances[name] = chance
        verdicts[name] = cuts[signal.cut].verdict(chance)
    return verdicts, chances
