"""The owner's bounded exception: a spoken yes approves only from an active version's answer in
time; a shadow, an unsure answer or a fallback never does, and a changed outcome that leaves any
other way is the rule's and pages (ADR 0069, Leo §8.4)."""

import uuid

from shosai.core.ai.decisions import NoulAnswer
from shosai.core.ai.errors import AiFailure
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.contracts.voice import VoiceApprovalFacts
from shosai.features.decisions.application.engine import within_bounds
from shosai.features.decisions.channels.agent_ports import AgentVoiceApprovalJudge
from shosai.features.decisions.contracts import (
    DecisionReason,
    DecisionSource,
    Outcome,
    VoiceConsent,
)
from shosai.features.decisions.domain.policies.voice_approval import VOICE_APPROVAL as POLICY
from shosai.features.decisions.domain.verdicts import Cut
from tests.features.decisions.engine_bench import Bench, bench, stored

CUTS = {"approves": Cut(lower=0.9, upper=0.95)}
ACTIVE = stored(POLICY, "active", CUTS)
SHADOW = stored(POLICY, "shadow", CUTS)
CONSENTS = "shosai_decision_consents_total"
OUTSIDE = "shosai_decision_outcomes_outside_bounds_total"


def reply(utterance: str = "да, давай") -> VoiceApprovalFacts:
    """A reply to a card Leo read back, in the EU home with consent."""
    return VoiceApprovalFacts(
        read_back="Создать задачу\nНазвание: Позвонить Анне\nСрок: пятница",
        utterance=utterance, language="ru", scope=TenancyScope(Home.EU, uuid.uuid4()),
        cross_border_consent=True, action_id=uuid.uuid4(),
    )  # fmt: skip


def counted(test: Bench, name: str) -> float:
    """A counter of the point."""
    return test.sample(name, point="voice.approval")


async def test_an_active_version_s_sure_yes_approves_and_is_counted() -> None:
    test = bench(ACTIVE)
    test.jev.answers = {"approves": NoulAnswer(0.99)}

    approved = await AgentVoiceApprovalJudge(test.engine).approved(reply())

    assert approved is True
    assert (counted(test, CONSENTS), counted(test, OUTSIDE)) == (1, 0)
    assert test.sample("shosai_decision_unsafe_outcomes_total", point="voice.approval") == 0
    [(_, row)] = test.rows.decisions
    assert (row["rule_outcome"], row["outcome"], row["source"]) == ("not_given", "given", "jev")


async def test_a_shadow_an_unsure_answer_or_a_failure_never_approves() -> None:
    shadow, unsure, failing = bench(SHADOW), bench(ACTIVE), bench(ACTIVE)
    shadow.jev.answers = {"approves": NoulAnswer(0.99)}
    unsure.jev.answers = {"approves": NoulAnswer(0.92)}
    failing.jev.failure = AiFailure.PROVIDER_ERROR

    approved = [
        await AgentVoiceApprovalJudge(test.engine).approved(reply())
        for test in (shadow, unsure, failing)
    ]
    await shadow.engine.drain()

    assert approved == [None, None, None]
    assert [counted(test, CONSENTS) for test in (shadow, unsure, failing)] == [0, 0, 0]


async def test_the_judge_is_ready_only_while_an_active_version_is_in_force() -> None:
    ready = [
        await AgentVoiceApprovalJudge(test.engine).ready()
        for test in (bench(ACTIVE), bench(SHADOW), bench())
    ]

    assert ready == [True, False, False]


async def test_an_empty_reply_asks_nothing() -> None:
    test = bench(ACTIVE)

    approved = await AgentVoiceApprovalJudge(test.engine).approved(reply("   "))

    assert approved is None
    assert test.jev.asked == []


def test_only_jev_s_answer_in_time_may_change_an_outcome() -> None:
    rule, given = VoiceConsent.NOT_GIVEN, VoiceConsent.GIVEN

    assert within_bounds(rule, Outcome(given, DecisionReason.JUDGED, DecisionSource.JEV))
    assert within_bounds(rule, Outcome(rule, DecisionReason.DEADLINE, DecisionSource.FALLBACK))
    for reason, source in (
        (DecisionReason.POLICY_OFF, DecisionSource.RULE),
        (DecisionReason.DEADLINE, DecisionSource.FALLBACK),
        (DecisionReason.DEADLINE, DecisionSource.LATE),
    ):
        assert not within_bounds(rule, Outcome(given, reason, source))
