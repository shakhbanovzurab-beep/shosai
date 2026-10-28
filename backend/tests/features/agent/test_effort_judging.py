"""How hard a turn's model reasons, judged beside the rule (agent step 21; decisions'
`turn.effort`, the owner's ChatGPT-like "Auto" of 2026-10-27).

A bound judge reads the question while the context is read; only its sure "deep" raises the
turn's model to `medium`. An unsure, late or absent answer keeps the tier's effort, and a turn
the person asked to think longer reasons at `high` without asking the judge.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field

import pytest

from shosai.core.ai.requests import ReasoningEffort
from shosai.features.agent.application.effort_judging import EFFORT_WAIT
from shosai.features.agent.contracts.effort import EffortJudge, EffortRequest
from tests.features.agent.tool_doubles import saying
from tests.features.agent.turn_bench import TurnBench


@dataclass
class RecordingJudge:
    """Answers every turn the same way, after a delay; keeps what it was asked."""

    answer: bool | None = True
    delay: float = 0.0
    asked: list[EffortRequest] = field(default_factory=list)

    async def deep(self, request: EffortRequest) -> bool | None:
        """The answer set for the test."""
        self.asked.append(request)
        await asyncio.sleep(self.delay)
        return self.answer


@pytest.fixture
def judge() -> RecordingJudge:
    """The judge bound for this module's turns."""
    return RecordingJudge()


@pytest.fixture
def effort_judges(judge: RecordingJudge) -> tuple[EffortJudge, ...]:
    """The recording judge beside the rule."""
    return (judge,)


async def test_a_question_judged_deep_reasons_at_medium_and_the_rest_keep_the_rule(
    turn_bench: TurnBench, judge: RecordingJudge
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [saying("A plan."), saying("Hi!")]

    await turn_bench.ask(person, thread, "Plan my quarter against the budget.")
    judge.answer = None
    await turn_bench.ask(person, thread, "Hi!")

    assert [call.reasoning for call in turn_bench.model.calls] == [ReasoningEffort.MEDIUM, None]
    first, second = judge.asked
    assert (first.question, first.previous, first.files, first.turn) == (
        "Plan my quarter against the budget.", "", 0, 0,
    )  # fmt: skip
    assert (second.previous, second.turn, second.scope.user_id) == ("A plan.", 1, person)


async def test_think_longer_is_never_asked_and_a_slow_judge_is_not_waited_for(
    turn_bench: TurnBench, judge: RecordingJudge
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [saying("Thought."), saying("Quick.")]

    await turn_bench.ask(person, thread, "Compare the offers.", think_longer=True)
    judge.delay = 3.0
    started = time.monotonic()
    await turn_bench.ask(person, thread, "Thanks.")
    waited = time.monotonic() - started

    assert [call.reasoning for call in turn_bench.model.calls] == [ReasoningEffort.HIGH, None]
    assert [request.question for request in judge.asked] == ["Thanks."]
    assert waited < EFFORT_WAIT.total_seconds() + 1.5
