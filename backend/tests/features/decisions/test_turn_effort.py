"""`turn.effort`: a turn's reasoning raised only by an active version's sure "deep", never by a
shadow, an unsure answer or a failure, and never below the rule (agent step 21; ChatGPT's
"Auto" as the owner chose it on 2026-10-27)."""

import uuid

from shosai.core.ai.decisions import NoulAnswer
from shosai.core.ai.errors import AiFailure
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.contracts.effort import EffortRequest
from shosai.features.decisions.channels.agent_ports import AgentEffortJudge
from shosai.features.decisions.domain.policies.turn_effort import TURN_EFFORT as POLICY
from shosai.features.decisions.domain.policies.turn_effort import EffortFacts, TurnEffort
from shosai.features.decisions.domain.verdicts import Cut
from tests.features.decisions.engine_bench import bench, stored

CUTS = {"deliberate": Cut(lower=0.6, upper=0.8)}
ACTIVE = stored(POLICY, "active", CUTS)
SHADOW = stored(POLICY, "shadow", CUTS)


def asked(
    question: str = "Compare the three offers and draft a plan for next quarter.",
) -> EffortRequest:
    """A turn's question in the EU home with consent."""
    return EffortRequest(
        question=question, previous="", section="tasks", files=0, turn=2, language="en",
        scope=TenancyScope(Home.EU, uuid.uuid4()), cross_border_consent=True,
        run_id=uuid.uuid4(),
    )  # fmt: skip


async def test_an_active_version_s_sure_deep_raises_the_turn() -> None:
    test = bench(ACTIVE)
    test.jev.answers = {"deliberate": NoulAnswer(0.95)}

    deep = await AgentEffortJudge(test.engine).deep(asked())

    assert deep is True
    [(_, row)] = test.rows.decisions
    assert (row["rule_outcome"], row["outcome"], row["source"]) == ("standard", "deep", "jev")


async def test_a_shadow_an_unsure_answer_or_a_failure_keeps_the_rule() -> None:
    shadow, unsure, failing = bench(SHADOW), bench(ACTIVE), bench(ACTIVE)
    shadow.jev.answers = {"deliberate": NoulAnswer(0.95)}
    unsure.jev.answers = {"deliberate": NoulAnswer(0.7)}
    failing.jev.failure = AiFailure.PROVIDER_ERROR

    deep = [await AgentEffortJudge(test.engine).deep(asked()) for test in (shadow, unsure, failing)]
    await shadow.engine.drain()

    assert deep == [None, None, None]


async def test_an_empty_question_asks_nothing() -> None:
    test = bench(ACTIVE)

    deep = await AgentEffortJudge(test.engine).deep(asked("   "))

    assert deep is None
    assert test.jev.asked == []


def test_a_judgement_only_raises_the_rule_s_effort() -> None:
    facts = EffortFacts(question="Hi", previous="", section="", files=0, turn=0)

    assert POLICY.careful(TurnEffort.DEEP, TurnEffort.STANDARD) is TurnEffort.DEEP
    assert POLICY.less_careful(TurnEffort.STANDARD, TurnEffort.DEEP)
    assert not POLICY.less_careful(TurnEffort.DEEP, TurnEffort.STANDARD)
    assert POLICY.settled(facts, TurnEffort.DEEP)
    assert (
        POLICY.parse_facts({"question": "Hi", "previous": "", "section": "", "files": 0, "turn": 0})
        == facts
    )
