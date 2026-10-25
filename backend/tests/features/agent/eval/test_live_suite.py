"""The live suite's run, scores and report, with a stand-in for the real model (agent step 8).

The suite asks a model each scenario in each language and a judge grades each answer; here the
model always answers in a sentence and the judge always passes, so the scores are known. A turn
the platform refuses is a failed case, never the end of the run, and a turn that ends on a card
shows the judge the card's values.
"""

import json
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from typing import Final

from redis.asyncio import Redis

from shosai.core.ai.calls import CallContext, ModelRoute
from shosai.core.ai.requests import ChatRequest
from shosai.core.ai.results import ChatDelta, ChatResult, Usage
from shosai.features.agent.application.eval_judge import Judge
from shosai.features.agent.application.eval_model import SCRIPTED, SCRIPTED_ROUTE, ScriptedRounds
from shosai.features.agent.application.eval_runner import EvalRunner
from shosai.features.agent.application.eval_suites import LiveSuite
from shosai.features.agent.application.run_context import text_of
from shosai.features.agent.domain.eval_report import LiveBaseline, live_regressions, summarize
from shosai.features.agent.infrastructure.eval_files import live_report_markdown, load_scenarios
from tests.features.agent.eval.conftest import eval_services
from tests.harness.database_access import DatabaseAccess

ANSWER: Final = "I am not sure."
GRADE: Final = {"language": True, "grounded": True, "helpful": 4, "reason": "Plain."}
SCENARIOS: Final = tuple(s for s in load_scenarios() if s.id in {"greeting", "overdue_tasks"})


class Plain:
    """A model that answers every question in one sentence, at a known cost."""

    async def stream_chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> AsyncIterator[ChatDelta]:
        """The sentence, then its usage."""
        del context, route, request
        yield ChatDelta(text=ANSWER)
        usage = Usage(input_tokens=10, output_tokens=4, reported_cost_usd=Decimal("0.001"))
        yield ChatDelta(finish_reason="stop", usage=usage, model=SCRIPTED)


class Passing:
    """A judge model that passes every answer and keeps what it was asked."""

    def __init__(self) -> None:
        self.asked: list[ChatRequest] = []

    async def chat(
        self, context: CallContext, route: ModelRoute, request: ChatRequest
    ) -> ChatResult:
        """The passing grade."""
        del context
        self.asked.append(request)
        return ChatResult(json.dumps(GRADE), (), "stop", route.primary, Usage())


async def test_the_live_suite_scores_each_case_and_compares_the_run_with_its_baseline(
    eval_runner: EvalRunner,
) -> None:
    suite = LiveSuite(eval_runner, Plain(), Judge(Passing(), SCRIPTED_ROUTE), concurrency=2)
    baseline = LiveBaseline(
        reason="test", recorded_on=date(2026, 10, 24), model="probe/leo",
        scores={"tool_choice": 0.9, "answers": 0.5, "judge": 1.0}, language_floor=0.6,
    )  # fmt: skip

    cases = await suite.run(SCENARIOS, ["en", "ja"])
    summary = summarize(cases)
    problems = live_regressions(summary, baseline)
    report = live_report_markdown(summary, cases, problems, "probe/leo")

    assert [(case.scenario, case.language) for case in cases] == [
        ("greeting", "en"), ("greeting", "ja"), ("overdue_tasks", "en"), ("overdue_tasks", "ja"),
    ]  # fmt: skip
    assert all(case.answer == ANSWER for case in cases)
    assert dict(summary.scores) == {"tool_choice": 0.5, "answers": 0.5, "judge": 1.0}
    assert dict(summary.languages) == {"en": 0.5, "ja": 0.5}
    assert summary.cost_usd == Decimal("0.004")
    assert problems == [
        "tool_choice: 50.0% is more than 3 points below 90.0%",
        "tool_choice: 50.0% below the baseline",
        "language en: tool choice 50.0% below the floor 60.0%",
        "language ja: tool choice 50.0% below the floor 60.0%",
    ]
    assert "`overdue_tasks` (ja): missing calls ['tasks.search']" in report


async def test_a_turn_the_platform_refuses_is_a_failed_case(
    homes: DatabaseAccess, valkey: Redis
) -> None:
    # Без живого воркера агента в парке ход не допускается: 429 agent_busy.
    idle = EvalRunner(eval_services(homes, valkey), SCRIPTED_ROUTE)

    (case,) = await LiveSuite(idle, Plain(), None, concurrency=1).run(SCENARIOS[:1], ["en"])

    assert case.tool_problems == ("turn refused: agent_busy",)
    assert case.judge is None


async def test_the_judge_sees_the_card_a_paused_turn_proposed(eval_runner: EvalRunner) -> None:
    (scenario,) = (s for s in load_scenarios() if s.id == "task_proposal")
    judge = Passing()
    suite = LiveSuite(
        eval_runner, ScriptedRounds(scenario.script), Judge(judge, SCRIPTED_ROUTE), concurrency=1
    )

    (case,) = await suite.run([scenario], ["en"])

    (asked,) = judge.asked
    case_text = text_of(asked.messages[-1])
    assert case.answer == ""
    assert case.tool_problems == ()
    assert '- tasks.create with {"tasks": [{"title": "Call Anna"' in case_text
    assert "No card." not in case_text
