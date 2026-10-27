"""From Jev's answers to verdicts: a probability per signal, read through a cut with a margin.

Jev is not deterministic (Leo §6.1): the same state may answer 0.79 and then 0.84, and its
stated probabilities need not match its observed frequencies for a given question. So each
cut carries a curve fitted per policy version that turns Jev's probability into a calibrated
one (ADR 0069, the owner's amendment of 2026-10-27); no exact value decides — the calibrated
probability is compared with the cut, and one inside the cut's unsure band is `UNSURE`, which
each policy reads as its careful side (ADR 0026 point 5).

A signal names the cut it is read through and how its probability comes out of an answer:
a `noul` gives it directly, a `choice` by one option, a `score` as the chance the level is at
least the one named.
"""

import bisect
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


type Curve = tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class Cut:
    """The edges of the unsure band: below `lower` is NO, from `upper` YES, between unsure;
    and the curve that turns Jev's probability into a calibrated one before the edges read it.

    Edges, not a threshold and a margin: a fitted edge is kept exactly as fitted, with no
    arithmetic that could move a case across it. The curve's knots are (Jev's probability,
    calibrated probability), both non-decreasing; no curve reads the probability as it is.
    """

    lower: float
    upper: float
    curve: Curve = ()

    def __post_init__(self) -> None:
        if not 0 <= self.lower <= self.upper <= 1 or self.upper - self.lower > 2 * MAX_MARGIN:
            message = "порог: края от 0 до 1, нижний не выше верхнего, полоса не шире 1"
            raise ValueError(message)
        points = [value for knot in self.curve for value in knot]
        steps = zip(self.curve, self.curve[1:], strict=False)
        if not all(0 <= value <= 1 for value in points) or not all(
            left[0] <= right[0] and left[1] <= right[1] for left, right in steps
        ):
            message = "кривая поправки: точки от 0 до 1, обе координаты не убывают"
            raise ValueError(message)

    def calibrated(self, probability: float) -> float:
        """Jev's probability read through the curve."""
        return on_curve(self.curve, probability)

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
        cut = cuts[signal.cut]
        chance = cut.calibrated(probability(answer, signal))
        chances[name] = chance
        verdicts[name] = cut.verdict(chance)
    return verdicts, chances


def on_curve(curve: Curve, probability: float) -> float:
    """A probability through a curve: straight between knots, flat past the ends; with no
    knots, as it is."""
    if not curve:
        return probability
    if probability <= curve[0][0]:
        return curve[0][1]
    if probability >= curve[-1][0]:
        return curve[-1][1]
    right = bisect.bisect_right(curve, probability, key=lambda knot: knot[0])
    (x0, y0), (x1, y1) = curve[right - 1], curve[right]
    if x1 == x0:
        return y1
    return y0 + (y1 - y0) * (probability - x0) / (x1 - x0)
