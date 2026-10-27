"""A card's friction from the rule and a bound judge; every card's end told to the judge
(decisions step 5; ADR 0068 AG-D7, ADR 0069 DL-D4).

The probe's write is reversible and the run read nothing from outside, so the rule leaves its
card standard and the judge is asked, with the person's question and the card as they read it.
"""

import uuid
from dataclasses import dataclass, field

import pytest

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.spec import Reversibility
from shosai.core.kernel.homes import Home
from shosai.features.agent.contracts import CardEnd, Friction, FrictionFacts, FrictionJudge
from tests.features.agent.action_bench import ActionBench
from tests.features.agent.turn_bench import HOME

FRICTION = "SELECT friction FROM agent_actions WHERE id = %s"


@dataclass
class RecordingJudge:
    """Answers every card the same way and keeps what it was asked and told."""

    answer: Friction | None = Friction.WARNING
    asked: list[FrictionFacts] = field(default_factory=list)
    ends: list[tuple[Home, uuid.UUID, CardEnd]] = field(default_factory=list)

    async def judge(self, facts: FrictionFacts) -> Friction | None:
        """The answer set for the test."""
        self.asked.append(facts)
        return self.answer

    def ended(self, home: Home, action_id: uuid.UUID, end: CardEnd) -> None:
        """Keep the card's end."""
        self.ends.append((home, action_id, end))


@pytest.fixture
def judge() -> RecordingJudge:
    """The judge bound for this module's turns."""
    return RecordingJudge()


@pytest.fixture
def friction_judges(judge: RecordingJudge) -> tuple[FrictionJudge, ...]:
    """The recording judge beside the rule."""
    return (judge,)


async def test_a_judge_that_asks_for_more_turns_the_card_into_a_warning(
    action_bench: ActionBench, judge: RecordingJudge
) -> None:
    person = uuid.uuid4()

    card = (await action_bench.paused_turn(person, "Make the task Call Anna."))["card"]
    action_id = uuid.UUID(card["id"])
    stored = await action_bench.rows(FRICTION, action_id)

    assert (card["warning"], stored) == (True, [{"friction": int(Friction.WARNING)}])
    facts = judge.asked[0]
    assert (facts.tool, facts.toolset, facts.rule) == ("tasks.create", "tasks", Friction.STANDARD)
    assert (facts.reversibility, facts.taint) == (Reversibility.REVERSIBLE, Taint.NONE)
    assert (facts.question, facts.language) == ("Make the task Call Anna.", "en")
    assert facts.card.splitlines()[0] == "Probe write"
    assert (facts.items, facts.other_space, facts.action_id) == (1, False, action_id)
    assert (facts.scope.home, facts.scope.user_id) == (HOME, person)


async def test_a_judge_with_nothing_to_add_leaves_the_rule_s_card(
    action_bench: ActionBench, judge: RecordingJudge
) -> None:
    judge.answer = None

    card = (await action_bench.paused_turn(uuid.uuid4()))["card"]

    assert card["warning"] is False
    assert await action_bench.rows(FRICTION, uuid.UUID(card["id"])) == [{"friction": 0}]


async def test_every_card_s_end_is_told_to_the_judge_once(
    action_bench: ActionBench, judge: RecordingJudge
) -> None:
    judge.answer = None
    people = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    approved, rejected, expired = [
        (await action_bench.paused_turn(person))["card"] for person in people
    ]
    await action_bench.move(
        "UPDATE agent_actions SET expires_at = now() - interval '1 second' WHERE id = %s",
        uuid.UUID(expired["id"]),
    )

    await action_bench.decide(people[0], approved, "approve")
    await action_bench.decide(people[1], rejected, "reject")
    await action_bench.sweep()
    await action_bench.queue.settle()

    assert judge.ends == [
        (HOME, uuid.UUID(approved["id"]), CardEnd.APPROVED),
        (HOME, uuid.UUID(rejected["id"]), CardEnd.REJECTED),
        (HOME, uuid.UUID(expired["id"]), CardEnd.EXPIRED),
    ]
