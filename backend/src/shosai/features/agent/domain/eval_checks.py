"""What a run of a scenario did, and how it is judged (AG-D8, Leo §11.4).

`Observed` is one turn seen from outside: the tools the model called, the calls that reached a
tool, the stream's events, the answer, and every model call's input — its text, its tools and
its estimated tokens. A trajectory passes when the expected tools ran with the arguments that
matter, nothing to avoid ran, and the answer was given, names what it must and cites when it
must; in CI with the scripted model the tools must run exactly as expected. The context stays
within its segments' caps and a first round within 12 000 tokens (L-N3); the cost of a scenario
— model calls and tokens — may not grow by more than a tenth of its baseline.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from pydantic import JsonValue

from shosai.features.agent.domain.budgets import SEGMENT_CAPS, Segment
from shosai.features.agent.domain.eval_cases import EvalExpectation

FIRST_ROUND_TOKENS: Final = 12_000
COST_TOLERANCE: Final = 0.10
ANSWERED: Final = "answered"
PAUSED: Final = "paused"
CITATION: Final = re.compile(r"\[\d{1,2}\]")


@dataclass(frozen=True, slots=True)
class ToolRun:
    """A call that reached a tool: its arguments as validated, the run's taint at the time."""

    tool: str
    effect: str
    arguments: Mapping[str, JsonValue]
    taint: int


@dataclass(frozen=True, slots=True)
class ModelCall:
    """One call of the model: what it read, the tools it was offered, what it used."""

    text: str
    tools: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal | None = None
    # Входные токены по счёту провайдера; None — провайдер не сказал (сценарная модель).
    reported_input_tokens: int | None = None
    # Модель, которая ответила, как её назвал провайдер: при отказе основной — запасная.
    model: str | None = None


@dataclass(frozen=True, slots=True)
class Card:
    """A card the turn proposed, as its stream showed it."""

    tool: str
    warning: bool
    taint: str | None


@dataclass(frozen=True, slots=True)
class Observed:
    """One turn of a scenario, seen from outside."""

    # Инструменты, которые вызывала модель, по порядку, с точкой в имени.
    attempted: tuple[str, ...]
    runs: tuple[ToolRun, ...]
    events: tuple[str, ...]
    outcome: str | None
    answer: str
    sources: int
    navigations: tuple[str, ...]
    calls: tuple[ModelCall, ...]
    # Сегменты первого вызова модели, оценка в токенах.
    segments: Mapping[Segment, int] = field(default_factory=dict)
    # Голова контекста и схемы инструментов первого вызова: стабильны от хода к ходу.
    head: str = ""
    tools_schema: str = ""
    # Карточки, которые ход предложил: инструмент, предупреждение и метка порчи.
    cards: tuple[Card, ...] = ()
    # Записи, которые срез спланировал для карточек, с аргументами: их видит судья.
    proposed: tuple[ToolRun, ...] = ()

    def ran(self, tool: str) -> tuple[ToolRun, ...]:
        """The calls of a tool that ran."""
        return tuple(run for run in self.runs if run.tool == tool)


@dataclass(frozen=True, slots=True)
class Verdict:
    """Whether a turn did what the scenario expects, and what it missed."""

    problems: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """No problem found."""
        return not self.problems


def first_calls(attempted: Sequence[str]) -> tuple[str, ...]:
    """The tools in the order each was first called."""
    return tuple(dict.fromkeys(attempted))


def trajectory_verdict(expect: EvalExpectation, observed: Observed, *, exact: bool) -> Verdict:
    """The trajectory against the scenario: `exact` for the scripted model in CI."""
    problems = tool_problems(expect, observed, exact=exact)
    problems.extend(answer_problems(expect, observed))
    return Verdict(tuple(problems))


def tool_problems(expect: EvalExpectation, observed: Observed, *, exact: bool) -> list[str]:
    """Where the tools called, or their arguments, differ from the scenario's."""
    problems: list[str] = []
    called = first_calls(observed.attempted)
    if exact and called != expect.calls:
        problems.append(f"calls {list(called)} instead of {list(expect.calls)}")
    missing = [tool for tool in expect.calls if tool not in called]
    if not exact and missing:
        problems.append(f"missing calls {missing}")
    if expect.quiet and called:
        problems.append(f"tools called in a quiet turn: {list(called)}")
    avoided = [tool for tool in expect.avoid if tool in called]
    if avoided:
        problems.append(f"called tools to avoid {avoided}")
    problems.extend(argument_problems(expect, observed))
    return problems


def not_run(reads: Sequence[str], observed: Observed) -> list[str]:
    """Expected reads the model called but no tool answered: refused, never offered."""
    return [
        f"{tool} was called but did not run"
        for tool in reads
        if tool in observed.attempted and not observed.ran(tool)
    ]


def argument_problems(expect: EvalExpectation, observed: Observed) -> list[str]:
    """Fields of the first run of each tool that differ from what the scenario expects."""
    problems = []
    for tool, fields in expect.arguments.items():
        runs = observed.ran(tool)
        if not runs:
            continue
        for name, wanted in fields.items():
            got = runs[0].arguments.get(name)
            if not same_value(got, wanted):
                problems.append(f"{tool}.{name} = {got!r}, expected {wanted!r}")
    return problems


def same_value(got: JsonValue, wanted: JsonValue) -> bool:
    """Equal values; strings compared without case, as ids and enum values are."""
    if isinstance(got, str) and isinstance(wanted, str):
        return got.casefold() == wanted.casefold()
    return got == wanted


def answer_problems(expect: EvalExpectation, observed: Observed) -> list[str]:
    """What the answer lacks: an end as answered — or paused on its card when the scenario
    proposes a write — its words, its citations."""
    problems = []
    if expect.pauses:
        if observed.outcome != PAUSED or not observed.cards:
            problems.append(f"turn ended {observed.outcome} without its card")
    elif observed.outcome != ANSWERED:
        problems.append(f"turn ended {observed.outcome}")
    if not expect.pauses and not observed.answer.strip():
        problems.append("empty answer")
    text = observed.answer.casefold()
    absent = [word for word in expect.mentions if word.casefold() not in text]
    if absent:
        problems.append(f"answer does not name {absent}")
    if expect.cites and not (observed.sources and CITATION.search(observed.answer)):
        problems.append("answer cites no source")
    return problems


def budget_problems(observed: Observed) -> list[str]:
    """Segments over their caps, and a first round over 12 000 tokens."""
    problems = [
        f"segment {segment.value}: {tokens} > {SEGMENT_CAPS[segment]}"
        for segment, tokens in observed.segments.items()
        if tokens > SEGMENT_CAPS[segment]
    ]
    if observed.calls and observed.calls[0].input_tokens > FIRST_ROUND_TOKENS:
        problems.append(f"first round {observed.calls[0].input_tokens} > {FIRST_ROUND_TOKENS}")
    return problems


@dataclass(frozen=True, slots=True)
class CostLine:
    """What a scenario costs: model calls and tokens."""

    model_calls: int
    input_tokens: int
    output_tokens: int

    @classmethod
    def of(cls, observed: Sequence[Observed]) -> CostLine:
        """The sum over a scenario's turns."""
        calls = [call for turn in observed for call in turn.calls]
        return cls(
            len(calls),
            sum(call.input_tokens for call in calls),
            sum(call.output_tokens for call in calls),
        )


def cost_regressions(
    current: Mapping[str, CostLine],
    baseline: Mapping[str, CostLine],
    tolerance: float = COST_TOLERANCE,
) -> list[str]:
    """Scenarios that cost more than their baseline allows, or have no baseline at all."""
    problems = [f"{name}: no baseline" for name in sorted(set(current) - set(baseline))]
    problems += [
        f"{name}: baseline of no scenario" for name in sorted(set(baseline) - set(current))
    ]
    for name in sorted(set(current) & set(baseline)):
        now, then = current[name], baseline[name]
        for measure in ("model_calls", "input_tokens", "output_tokens"):
            value, limit = getattr(now, measure), getattr(then, measure) * (1 + tolerance)
            if value > limit:
                problems.append(f"{name}: {measure} {value} > {getattr(then, measure)} + 10%")
    return problems


def unstable_prefix(turns: Sequence[Observed]) -> list[str]:
    """Where a later turn's cached segments differ from the first turn's, byte for byte."""
    if not turns:
        return []
    first = turns[0]
    problems = []
    for number, turn in enumerate(turns[1:], start=2):
        if turn.head != first.head:
            problems.append(f"turn {number}: the policy and profile differ")
        if turn.tools_schema != first.tools_schema:
            problems.append(f"turn {number}: the tools differ")
    return problems
