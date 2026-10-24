"""The evaluation suites (Leo §11.4, AG-D8): the deterministic ones and the live one.

The deterministic suites play each scenario's script with the scripted model, so they run in
CI on every push with no key and no spend, and the same way through `shosai agent eval
--scripted`: the trajectory exactly as expected, the context within its caps in every
language and its cached head the same on a second turn, the cost against its baseline, and
every injection case without a violation. The live suite asks a real model each scenario in
each language and lets a judge grade the answers; a refused turn is a failed case, never the
end of the run.
"""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from shosai.core.kernel.errors import AppError
from shosai.features.agent.application.eval_judge import Judge
from shosai.features.agent.application.eval_model import ScriptedRounds
from shosai.features.agent.application.eval_runner import EvalRunner
from shosai.features.agent.application.run_engine_parts import ModelStreams
from shosai.features.agent.domain.eval_cases import EvalScenario, InjectionCorpus
from shosai.features.agent.domain.eval_checks import (
    CostLine,
    Observed,
    answer_problems,
    budget_problems,
    tool_problems,
    trajectory_verdict,
    unstable_prefix,
)
from shosai.features.agent.domain.eval_report import LiveCase
from shosai.features.agent.domain.eval_safety import UNSAFE_EFFECTS, injection_cases, violations

ENGLISH: Final = "en"
PREFIX_TURNS: Final = 2


@dataclass(frozen=True, slots=True)
class ScriptedOutcome:
    """A scenario played by the scripted model: what it got wrong, and what it cost."""

    problems: tuple[str, ...]
    cost: CostLine


def scripted(scenario: EvalScenario) -> Callable[[], ModelStreams]:
    """The scripted model for each turn of a scenario, from its first round."""
    return lambda: ScriptedRounds(scenario.script)


def unsafe_runs(observed: Observed) -> list[str]:
    """Writes and egress that ran: never, while nothing approves them."""
    return [
        f"{run.effect} ran: {run.tool}" for run in observed.runs if run.effect in UNSAFE_EFFECTS
    ]


async def scripted_trajectory(runner: EvalRunner, scenario: EvalScenario) -> ScriptedOutcome:
    """The scenario in English, twice in one thread: the trajectory, the budgets, the stable
    head, and the first turn's cost."""
    turns = await runner.run(scenario, ENGLISH, scripted(scenario), turns=PREFIX_TURNS)
    first = turns[0]
    problems = [
        *trajectory_verdict(scenario.expect, first, exact=True).problems,
        *unsafe_runs(first),
        *(problem for turn in turns for problem in budget_problems(turn)),
        *unstable_prefix(turns),
    ]
    return ScriptedOutcome(tuple(problems), CostLine.of(turns[:1]))


async def scripted_languages(
    runner: EvalRunner, scenario: EvalScenario, languages: Sequence[str]
) -> list[str]:
    """The scenario in each language at once: answered, within the budgets."""

    async def in_language(language: str) -> list[str]:
        (turn,) = await runner.run(scenario, language, scripted(scenario))
        found = [*answer_problems(scenario.expect, turn), *budget_problems(turn)]
        return [f"{language}: {problem}" for problem in found]

    found = await asyncio.gather(*(in_language(language) for language in languages))
    return [problem for problems in found for problem in problems]


async def safety_problems(runner: EvalRunner, corpus: InjectionCorpus) -> dict[str, list[str]]:
    """Every injection case with its violations; a safe case has none."""
    payloads = {payload.id: payload for payload in corpus.payloads}
    found: dict[str, list[str]] = {}
    for case in injection_cases(corpus):
        (turn,) = await runner.run(case, ENGLISH, scripted(case))
        payload = payloads[case.id.rsplit(".", 1)[-1]]
        found[case.id] = violations(turn, payload, corpus.probe)
    return found


class LiveSuite:
    """Each scenario in each language, answered by a real model and graded by a judge."""

    def __init__(
        self, runner: EvalRunner, model: ModelStreams, judge: Judge | None, concurrency: int
    ) -> None:
        self._runner = runner
        self._model = model
        self._judge = judge
        self._slots = asyncio.Semaphore(concurrency)

    async def run(
        self, scenarios: Sequence[EvalScenario], languages: Sequence[str]
    ) -> list[LiveCase]:
        """Every case, in the order of the scenarios, then the languages."""
        return list(
            await asyncio.gather(
                *(
                    self._case(scenario, language)
                    for scenario in scenarios
                    for language in languages
                )
            )
        )

    async def _case(self, scenario: EvalScenario, language: str) -> LiveCase:
        async with self._slots:
            try:
                (turn,) = await self._runner.run(scenario, language, lambda: self._model)
            except AppError as refused:
                problem = (f"turn refused: {refused.code}",)
                return LiveCase(
                    scenario.id, language, problem, problem, None, CostLine(0, 0, 0), None, ""
                )
            grade = await self._judge.grade(scenario, language, turn) if self._judge else None
        costs = [call.cost_usd for call in turn.calls if call.cost_usd is not None]
        return LiveCase(
            scenario=scenario.id,
            language=language,
            tool_problems=(*tool_problems(scenario.expect, turn, exact=False), *unsafe_runs(turn)),
            answer_problems=tuple(answer_problems(scenario.expect, turn)),
            judge=grade,
            cost=CostLine.of([turn]),
            cost_usd=sum(costs, Decimal(0)) if costs else None,
            answer=turn.answer,
        )
