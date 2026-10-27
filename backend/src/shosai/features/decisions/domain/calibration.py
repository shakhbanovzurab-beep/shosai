"""Calibration maths: fitting a cut, its calibration error, accuracy (Leo §6.4, ADR 0069).

A cut is fitted for a target precision of one side. Each cut also says which side an unsure
verdict joins — the side its policy reads it as — so the outcome's real boundary is the
edge between that side and the other: that edge is placed exactly where the fit put it,
and the unsure band (twice the margin wide) falls on the joined side. The fit takes the
boundary that keeps the most cases on the aimed side while its precision holds.

Expected calibration error (ECE) compares stated probabilities with observed frequencies,
in equal-width bins weighted by their size; the gate is ECE ≤ 0.05 (§6.4).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from shosai.features.decisions.domain.verdicts import MAX_MARGIN, Cut, Verdict

ECE_BINS: Final = 10
ECE_GATE: Final = 0.05

type Labelled = tuple[float, bool]


@dataclass(frozen=True, slots=True)
class CutAim:
    """The side whose precision a cut is fitted for, and the side an unsure verdict joins."""

    side: Verdict
    precision: float
    unsure_joins: Verdict

    def __post_init__(self) -> None:
        sides = (Verdict.YES, Verdict.NO)
        if self.side not in sides or self.unsure_joins not in sides:
            message = "сторона порога — YES или NO"
            raise ValueError(message)
        if not 0 < self.precision <= 1:
            message = "целевая точность — от 0 до 1"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class Aims:
    """A policy's targets: each cut's aim, the margin, the accuracy floor per language, and
    the share of careful cases its careful outcome must find (the accuracy floor by default)."""

    cuts: Mapping[str, CutAim]
    margin: float
    accuracy_floor: float
    careful_floor: float | None = None

    def __post_init__(self) -> None:
        floors = (self.accuracy_floor, self.careful_floor or self.accuracy_floor)
        if not 0 <= self.margin <= MAX_MARGIN or not all(0 < floor <= 1 for floor in floors):
            message = "поле неуверенности — до 0,5, пороги точности — от 0 до 1"
            raise ValueError(message)

    @property
    def careful(self) -> float:
        """The share of careful cases the careful outcome must find."""
        return self.careful_floor or self.accuracy_floor


def fit_cut(cases: Sequence[Labelled], aim: CutAim, margin: float) -> Cut | None:
    """The cut whose aimed side keeps the most cases at the target precision; None if no
    boundary reaches it. A case is (probability, whether the proposition is true)."""
    boundary = (yes_boundary if aim.side is Verdict.YES else no_boundary)(cases, aim.precision)
    if boundary is None:
        return None
    # Край исхода — граница между стороной, к которой примыкает «не уверен», и другой: он
    # ставится ровно в подобранную границу, полоса неуверенности ложится по эту сторону.
    if aim.unsure_joins is Verdict.YES:
        return Cut(lower=boundary, upper=min(boundary + 2 * margin, 1.0))
    return Cut(lower=max(boundary - 2 * margin, 0.0), upper=boundary)


def yes_boundary(cases: Sequence[Labelled], precision: float) -> float | None:
    """The lowest probability from which the cases are true at least at `precision`.

    A boundary falls only between distinct probabilities: equal ones go to the same side.
    """
    ordered = sorted(cases, key=lambda case: case[0], reverse=True)
    best: float | None = None
    hits = 0
    for count, (chance, label) in enumerate(ordered, start=1):
        hits += label
        group_ends = count == len(ordered) or ordered[count][0] < chance
        if group_ends and hits / count >= precision:
            best = chance
    return best


def no_boundary(cases: Sequence[Labelled], precision: float) -> float | None:
    """The highest boundary below which the cases are false at least at `precision`."""
    ordered = sorted(cases, key=lambda case: case[0])
    best: float | None = None
    hits = 0
    for count, (chance, label) in enumerate(ordered, start=1):
        hits += not label
        following = ordered[count][0] if count < len(ordered) else None
        group_ends = following is None or following > chance
        # Над вероятностью 1 границы нет: такие случаи не могут оказаться ниже неё.
        if group_ends and hits / count >= precision and chance < 1:
            # Граница — следующая вероятность (она уже выше), после последней — ближайшее
            # число над ней: без деления, которое на крохотных числах округлится вниз.
            best = following if following is not None else math.nextafter(chance, 1.0)
    return best


def expected_calibration_error(cases: Sequence[Labelled], bins: int = ECE_BINS) -> float:
    """The weighted gap between stated probability and observed frequency, per bin."""
    if not cases:
        return 0.0
    sums: list[list[float]] = [[0.0, 0.0, 0.0] for _ in range(bins)]
    for chance, label in cases:
        bucket = sums[min(int(chance * bins), bins - 1)]
        bucket[0] += 1
        bucket[1] += chance
        bucket[2] += label
    gap = sum(abs(stated - seen) for count, stated, seen in sums if count)
    return gap / len(cases)


def accuracy(agreements: Sequence[bool]) -> float:
    """The share of cases where the outcome was the labelled one; 0 for none."""
    return sum(agreements) / len(agreements) if agreements else 0.0
