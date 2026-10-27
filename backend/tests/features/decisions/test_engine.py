"""The engine: the rule first, Jev within its deadline, a fallback for every failure, a record
per consulted decision and none of its text (decisions plan §3.3, ADR 0026, ADR 0069)."""

import asyncio
import uuid
from datetime import timedelta

import pytest

from shosai.core.agent_tools.spec import Reversibility
from shosai.core.ai.calls import CallClass, CallOrigin
from shosai.core.ai.errors import AiFailure
from shosai.core.kernel.homes import Home
from shosai.features.decisions.contracts import (
    ACTION_FRICTION,
    CardFriction,
    CardResolution,
    DecisionReason,
    DecisionSource,
)
from shosai.features.decisions.domain.outcomes import Subject, SubjectKind
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION as POLICY
from tests.features.decisions.engine_bench import FRICTION_CUTS, bench, card_call, matching, stored

ACTIVE = stored(POLICY, "active", FRICTION_CUTS)


async def test_without_a_policy_in_force_the_rule_decides_and_nothing_is_recorded() -> None:
    test = bench()

    outcome = await test.engine.decide(ACTION_FRICTION, card_call())

    assert (outcome.value, outcome.reason, outcome.source) == (
        CardFriction.STANDARD, DecisionReason.POLICY_OFF, DecisionSource.RULE,
    )  # fmt: skip
    assert (test.jev.asked, test.rows.decisions) == ([], [])
    labels = {"point": "action.friction", "source": "rule", "reason": "policy_off", "changed": "no"}
    assert test.sample("shosai_decision_requests_total", **labels) == 1


@pytest.mark.parametrize(
    ("rule", "reversibility"),
    [
        (CardFriction.WARNING, Reversibility.REVERSIBLE),
        (CardFriction.STANDARD, Reversibility.IRREVERSIBLE),
    ],
)
async def test_nothing_is_asked_when_the_rule_cannot_change(
    rule: CardFriction, reversibility: Reversibility
) -> None:
    test = bench(ACTIVE)

    outcome = await test.engine.decide(
        ACTION_FRICTION, card_call(rule, reversibility=reversibility)
    )

    assert (outcome.value, outcome.reason) == (rule, DecisionReason.NOTHING_TO_DECIDE)
    assert (test.jev.asked, test.rows.decisions) == ([], [])


async def test_a_sure_answer_in_time_judges_and_is_recorded_without_text() -> None:
    test = bench(ACTIVE)
    test.jev.answers = matching(narrow=False)
    call = card_call()

    outcome = await test.engine.decide(ACTION_FRICTION, call)

    assert (outcome.value, outcome.reason, outcome.source, outcome.policy) == (
        CardFriction.WARNING, DecisionReason.JUDGED, DecisionSource.JEV, "action.friction@1",
    )  # fmt: skip
    [(context, request)] = test.jev.asked
    assert context.effect_key == f"decision:{outcome.decision_id}"
    assert (context.origin, context.call_class) == (CallOrigin.BACKGROUND, CallClass.STANDARD)
    assert (context.feature, context.scope) == ("decisions.action.friction", call.scope)
    assert context.deadline == timedelta(milliseconds=1_200)
    assert set(request.questions) == {"matches_request", "reach"}
    [(home, row)] = test.rows.decisions
    assert (home, row["id"], row["subject_id"]) == (Home.EU, outcome.decision_id, call.subject.id)
    assert (row["rule_outcome"], row["outcome"], row["source"]) == ("standard", "warning", "jev")
    assert row["probabilities"] == {"matches_request": 0.95, "reach": pytest.approx(0.9)}
    assert row["jev_snapshot"] == "typesafe/jev-1.13-20260917"
    assert len(row["state_hash"]) == 16
    written = repr(row) + repr([span.attributes for span in test.spans.get_finished_spans()])
    assert "задач" not in written
    assert "Отчёт" not in written


async def test_a_sure_match_that_stays_narrow_keeps_the_card_standard() -> None:
    test = bench(ACTIVE)
    test.jev.answers = matching(narrow=True)

    outcome = await test.engine.decide(ACTION_FRICTION, card_call())

    assert (outcome.value, outcome.source) == (CardFriction.STANDARD, DecisionSource.JEV)


# Дом, согласие, нулевое хранение у Jev — и причина, по которой его не спрашивают.
BLOCKED = [
    (Home.RU, False, True, DecisionReason.NO_CONSENT),
    (Home.EU, True, False, DecisionReason.NOT_ZDR),
]


@pytest.mark.parametrize("case", BLOCKED)
async def test_a_blocked_decision_is_the_rules_recorded_without_a_call(
    case: tuple[Home, bool, bool, DecisionReason],
) -> None:
    home, consent, keeps_nothing, reason = case
    test = bench(ACTIVE)
    test.terms.keeps_nothing = keeps_nothing

    outcome = await test.engine.decide(ACTION_FRICTION, card_call(home=home, consent=consent))

    assert (outcome.value, outcome.reason, outcome.source) == (
        CardFriction.STANDARD, reason, DecisionSource.FALLBACK,
    )  # fmt: skip
    assert test.jev.asked == []
    [(written_in, row)] = test.rows.decisions
    assert (written_in, row["reason"], row["source"]) == (home, reason.value, "fallback")


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (AiFailure.SPEND_LIMIT, DecisionReason.BUDGET),
        (AiFailure.CONSENT_REQUIRED, DecisionReason.NO_CONSENT),
        (AiFailure.PROVIDER_ERROR, DecisionReason.PROVIDER_ERROR),
        (AiFailure.RATE_LIMITED, DecisionReason.PROVIDER_ERROR),
        (AiFailure.INPUT_TOO_LARGE, DecisionReason.CONTRACT),
    ],
)
async def test_a_failed_call_is_the_rules_outcome_with_its_reason(
    failure: AiFailure, reason: DecisionReason
) -> None:
    test = bench(ACTIVE)
    test.jev.failure = failure

    outcome = await test.engine.decide(ACTION_FRICTION, card_call())

    assert (outcome.value, outcome.reason, outcome.source) == (
        CardFriction.STANDARD, reason, DecisionSource.FALLBACK,
    )  # fmt: skip
    [(_, row)] = test.rows.decisions
    assert (row["reason"], row["probabilities"]) == (reason.value, {})


async def test_a_late_answer_leaves_the_rule_and_is_recorded_when_it_lands() -> None:
    test = bench(ACTIVE)
    test.jev.answers = matching(narrow=False)
    test.jev.delay = timedelta(milliseconds=600)

    outcome = await test.engine.decide(ACTION_FRICTION, card_call())

    assert (outcome.value, outcome.reason, outcome.source) == (
        CardFriction.STANDARD, DecisionReason.DEADLINE, DecisionSource.FALLBACK,
    )  # fmt: skip
    assert test.rows.decisions == []
    await test.engine.drain()
    [(_, row)] = test.rows.decisions
    assert (row["source"], row["reason"], row["outcome"]) == ("late", "deadline", "standard")
    assert row["probabilities"]["matches_request"] == 0.95
    assert test.sample("shosai_decision_late_total", point="action.friction") == 1


async def test_calls_in_flight_at_their_cap_answer_busy() -> None:
    test = bench(ACTIVE, max_in_flight=1)
    test.jev.answers = matching(narrow=True)
    test.jev.delay = timedelta(milliseconds=600)

    first = await test.engine.decide(ACTION_FRICTION, card_call())
    second = await test.engine.decide(ACTION_FRICTION, card_call())

    assert (first.reason, second.reason) == (DecisionReason.DEADLINE, DecisionReason.BUSY)
    assert len(test.jev.asked) == 1
    await test.engine.drain()


async def test_an_observation_is_kept_by_the_subject_in_its_home() -> None:
    test = bench(ACTIVE)
    subject = Subject(SubjectKind.ACTION, uuid.uuid4())

    test.engine.observe(ACTION_FRICTION, Home.RU, subject, CardResolution.REJECTED)

    [(home, row)] = test.rows.outcomes
    assert (home, row["point"], row["subject_id"]) == (Home.RU, "action.friction", subject.id)
    assert row["observation"] == {"resolution": "rejected"}


async def test_the_span_names_the_point_and_carries_no_text() -> None:
    test = bench(ACTIVE)
    test.jev.answers = matching(narrow=True)

    await test.engine.decide(ACTION_FRICTION, card_call())
    await asyncio.sleep(0)

    [span] = [s for s in test.spans.get_finished_spans() if s.name == "decision.action.friction"]
    assert dict(span.attributes or {}) == {
        "decision.source": "jev",
        "decision.reason": "judged",
        "decision.policy": "action.friction@1",
    }
