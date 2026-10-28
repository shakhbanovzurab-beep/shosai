"""Studio in the evaluation's world (studio step 11d): a turn's head takes the run's platform
layer after the policy core and the made-up person's "About you" — the scenario's own, else
the run's — where a real turn does, so the live suite measures the first round with them."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Final

from redis.asyncio import Redis

from shosai.features.agent.application.eval_model import SCRIPTED_ROUTE
from shosai.features.agent.application.eval_runner import EvalRunner
from shosai.features.agent.application.eval_studio import StudioWords
from shosai.features.agent.application.eval_suites import scripted
from shosai.features.agent.infrastructure.eval_files import load_scenarios
from shosai.features.agent.infrastructure.prompts import PERSONAL_CONTEXT, POLICY
from tests.features.agent.eval.conftest import eval_services
from tests.harness.database_access import DatabaseAccess

LAYER: Final = "Name the source of every fact."
ABOUT: Final = "I prefer answers in two sentences."
SCENARIOS: Final = {scenario.id: scenario for scenario in load_scenarios()}


@asynccontextmanager
async def runner_with(
    homes: DatabaseAccess, valkey: Redis, words: StudioWords
) -> AsyncIterator[EvalRunner]:
    """A runner whose turns take these Studio words, serving as an agent worker."""
    runner = EvalRunner(replace(eval_services(homes, valkey), studio=words), SCRIPTED_ROUTE)
    async with runner.serving():
        yield runner


async def test_the_head_takes_the_run_s_layer_and_about_you(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    scenario = SCENARIOS["greeting"]
    async with runner_with(homes, valkey, StudioWords(LAYER, ABOUT)) as runner:
        (turn,) = await runner.run(scenario, "en", scripted(scenario))

    assert turn.head.startswith(f"{POLICY}\n\n{LAYER}\n\n")
    assert PERSONAL_CONTEXT.format(context=ABOUT) in turn.head


async def test_a_scenario_s_own_about_you_wins_and_none_leaves_the_head_as_before(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    studio, greeting = SCENARIOS["studio_context"], SCENARIOS["greeting"]
    async with runner_with(homes, valkey, StudioWords(about=ABOUT)) as runner:
        (own,) = await runner.run(studio, "en", scripted(studio))
    async with runner_with(homes, valkey, StudioWords()) as runner:
        (plain,) = await runner.run(greeting, "en", scripted(greeting))

    assert PERSONAL_CONTEXT.format(context=studio.about) in own.head
    assert ABOUT not in own.head
    assert plain.head.startswith(f"{POLICY}\n\n")
    assert PERSONAL_CONTEXT.split("{", 1)[0] not in plain.head
