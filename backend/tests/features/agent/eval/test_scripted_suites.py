"""The deterministic suites CI runs on every push (agent step 8; Leo §11.4).

Each scenario is played by the scripted model through Leo's real turn: its trajectory exactly
as expected, its context within the caps and its cached head stable on a second turn, its
cost within a tenth of the baseline, and its answer within the budgets in all 16 languages.
"""

import pytest

from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.core.kernel.homes import Home
from shosai.features.agent.application.eval_runner import EvalRunner
from shosai.features.agent.application.eval_suites import scripted_languages, scripted_trajectory
from shosai.features.agent.domain.eval_cases import EvalScenario
from shosai.features.agent.domain.eval_checks import cost_regressions
from shosai.features.agent.infrastructure.eval_files import load_cost_baseline, load_scenarios
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

SCENARIOS = load_scenarios()
# Строки с содержимым стираются; прогоны (числа и коды) и ключи идемпотентности истекают сами,
# как у любого удалённого аккаунта (реестр удаления).
LEFT_BEHIND = (
    "SELECT (SELECT count(*) FROM agent_threads) + (SELECT count(*) FROM agent_messages)"
    " + (SELECT count(*) FROM agent_tool_results) + (SELECT count(*) FROM agent_settings) AS n"
)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.id)
async def test_a_scenario_runs_as_scripted_within_its_budgets_and_its_cost(
    eval_runner: EvalRunner, scenario: EvalScenario
) -> None:
    outcome = await scripted_trajectory(eval_runner, scenario)
    recorded = load_cost_baseline().lines()

    assert outcome.problems == ()
    assert cost_regressions({scenario.id: outcome.cost}, {scenario.id: recorded[scenario.id]}) == []


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.id)
async def test_a_scenario_is_answered_within_its_budgets_in_every_language(
    eval_runner: EvalRunner, scenario: EvalScenario
) -> None:
    assert await scripted_languages(eval_runner, scenario, SUPPORTED_LANGUAGES) == []


async def test_the_people_an_evaluation_makes_up_leave_nothing_behind(
    eval_runner: EvalRunner, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    del homes
    for scenario in SCENARIOS[:3]:
        await scripted_trajectory(eval_runner, scenario)

    left = await fetch_rows(run_slot.claimed.connections[Home.EU], LEFT_BEHIND, ())

    assert left[0]["n"] == 0
