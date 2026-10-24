"""What a live evaluation found, against the last recorded baseline (Leo §11.4, AG-D8).

Each case — a scenario in a language — scores in three suites: tool choice (the tools and the
arguments that matter), the answer (an answer, its words, its citations) and the judge's
grade. A run passes when no suite falls more than 3 points below the baseline, tool choice is
at least the baseline's, and every language keeps the floor. The baselines are files kept with
the slice; each records why it was set, so a cost or a score that moved has its reason.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from pydantic import Field

from shosai.features.agent.domain.eval_cases import Strict
from shosai.features.agent.domain.eval_checks import CostLine

SUITE_DROP: Final = 0.03
SUITES: Final = ("tool_choice", "answers", "judge")


@dataclass(frozen=True, slots=True)
class JudgeGrade:
    """The judge's grade of one answer."""

    language: bool
    grounded: bool
    helpful: int
    reason: str

    @property
    def passed(self) -> bool:
        """In the right language, grounded, and at least fairly helpful."""
        return self.language and self.grounded and self.helpful >= 3


@dataclass(frozen=True, slots=True)
class LiveCase:
    """One scenario in one language, as the live suite saw it."""

    scenario: str
    language: str
    tool_problems: tuple[str, ...]
    answer_problems: tuple[str, ...]
    # None — судья не оценивал: выключен или не ответил.
    judge: JudgeGrade | None
    cost: CostLine
    cost_usd: Decimal | None
    answer: str


@dataclass(frozen=True, slots=True)
class LiveSummary:
    """The suites' shares of passing cases, overall and by language, and what it cost."""

    cases: int
    scores: Mapping[str, float]
    languages: Mapping[str, float]
    cost: CostLine
    cost_usd: Decimal


def share(passed: int, total: int) -> float:
    """A share in [0, 1]; nothing to count is a full share."""
    return passed / total if total else 1.0


def summarize(cases: Sequence[LiveCase]) -> LiveSummary:
    """The suites over every case."""
    judged = [case.judge for case in cases if case.judge is not None]
    by_language: dict[str, list[LiveCase]] = defaultdict(list)
    for case in cases:
        by_language[case.language].append(case)
    scores = {
        "tool_choice": share(sum(not case.tool_problems for case in cases), len(cases)),
        "answers": share(sum(not case.answer_problems for case in cases), len(cases)),
        "judge": share(sum(grade.passed for grade in judged), len(judged)),
    }
    languages = {
        language: share(sum(not case.tool_problems for case in group), len(group))
        for language, group in sorted(by_language.items())
    }
    cost = CostLine(
        sum(case.cost.model_calls for case in cases),
        sum(case.cost.input_tokens for case in cases),
        sum(case.cost.output_tokens for case in cases),
    )
    spent = sum((case.cost_usd for case in cases if case.cost_usd is not None), Decimal(0))
    return LiveSummary(len(cases), scores, languages, cost, spent)


class Recorded(Strict):
    """Why and when a baseline was set."""

    reason: str = Field(min_length=1)
    recorded_on: date


class CostEntry(Strict):
    """One scenario's recorded cost."""

    model_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)

    @classmethod
    def of(cls, line: CostLine) -> CostEntry:
        """A scenario's cost as recorded."""
        return cls(
            model_calls=line.model_calls,
            input_tokens=line.input_tokens,
            output_tokens=line.output_tokens,
        )

    def line(self) -> CostLine:
        """As the checks count it."""
        return CostLine(self.model_calls, self.input_tokens, self.output_tokens)


class CostBaseline(Recorded):
    """The scripted scenarios' cost, as last recorded."""

    scenarios: dict[str, CostEntry]

    def lines(self) -> dict[str, CostLine]:
        """Each scenario's cost."""
        return {name: entry.line() for name, entry in self.scenarios.items()}


class LiveBaseline(Recorded):
    """The live suites' scores, as last recorded, with the model they were recorded on."""

    model: str = Field(min_length=1)
    scores: dict[str, float]
    language_floor: float = Field(ge=0, le=1)


def live_regressions(summary: LiveSummary, baseline: LiveBaseline) -> list[str]:
    """Where the live run fell below its baseline."""
    problems = []
    for suite in SUITES:
        now, then = summary.scores.get(suite, 0.0), baseline.scores.get(suite, 0.0)
        if now < then - SUITE_DROP:
            problems.append(f"{suite}: {now:.1%} is more than 3 points below {then:.1%}")
    tool_choice = summary.scores.get("tool_choice", 0.0)
    if tool_choice < baseline.scores.get("tool_choice", 0.0):
        problems.append(f"tool_choice: {tool_choice:.1%} below the baseline")
    problems += [
        f"language {language}: tool choice {score:.1%} below the floor "
        f"{baseline.language_floor:.1%}"
        for language, score in summary.languages.items()
        if score < baseline.language_floor
    ]
    return problems
