"""Shadow versions act on nothing; a policy that would soften the rule is caught (Leo §6.4,
ADR 0026 point 3)."""

from collections.abc import Mapping
from datetime import timedelta

from shosai.features.decisions.contracts import (
    ACTION_FRICTION,
    CardFacts,
    CardFriction,
    DecisionReason,
    DecisionSource,
)
from shosai.features.decisions.domain.policies.action_friction import (
    ACTION_FRICTION as POLICY,
)
from shosai.features.decisions.domain.policies.action_friction import ActionFriction
from shosai.features.decisions.domain.verdicts import Cut, Verdict
from tests.features.decisions.engine_bench import FRICTION_CUTS, bench, card_call, matching, stored

STRICT_CUTS = {"matches": Cut(lower=0.96, upper=0.99), "wide": Cut(lower=0.0, upper=0.05)}


class Version2(ActionFriction):
    """The same questions under the next version, as a shadow would be."""

    version = 2


class Reworded(ActionFriction):
    """A version whose questions differ, so it asks on its own."""

    version = 3

    def wording(self) -> Mapping[str, object]:
        """Different words, a different digest."""
        return {"reworded": True}


class Softening(ActionFriction):
    """A broken version that would turn a warning into a standard card."""

    version = 4

    def settled(self, facts: CardFacts, rule: CardFriction) -> bool:
        """Never settled, so the engine asks."""
        return False

    def careful(self, rule: CardFriction, judged: CardFriction) -> CardFriction:
        """The breach: the judged outcome even when lighter."""
        return judged

    def outcome(
        self, facts: CardFacts, verdicts: Mapping[str, Verdict], chances: Mapping[str, float]
    ) -> CardFriction:
        """Always standard."""
        return CardFriction.STANDARD


async def test_a_shadow_with_the_same_questions_reuses_the_answer_and_changes_nothing() -> None:
    shadow = Version2()
    test = bench(
        stored(POLICY, "active", FRICTION_CUTS),
        stored(shadow, "shadow", STRICT_CUTS),
        known=[shadow],
    )
    test.jev.answers = matching(narrow=True)

    outcome = await test.engine.decide(ACTION_FRICTION, card_call())

    assert (outcome.value, outcome.source) == (CardFriction.STANDARD, DecisionSource.JEV)
    assert len(test.jev.asked) == 1
    rows = {row["version"]: row for _, row in test.rows.decisions}
    assert (rows[1]["shadow"], rows[1]["outcome"]) == (False, "standard")
    # Тень с более строгими порогами предупредила бы — и только записала это.
    assert (rows[2]["shadow"], rows[2]["outcome"]) == (True, "warning")


async def test_a_shadow_with_its_own_questions_asks_on_its_own() -> None:
    shadow = Reworded()
    test = bench(
        stored(POLICY, "active", FRICTION_CUTS),
        stored(shadow, "shadow", FRICTION_CUTS),
        known=[shadow],
    )
    test.jev.answers = matching(narrow=True)

    await test.engine.decide(ACTION_FRICTION, card_call())
    await test.engine.drain()

    assert len(test.jev.asked) == 2
    assert sorted((row["version"], row["shadow"]) for _, row in test.rows.decisions) == [
        (1, False),
        (3, True),
    ]


async def test_a_shadow_alone_returns_the_rule_at_once_and_records_later() -> None:
    shadow = Version2()
    test = bench(stored(shadow, "shadow", FRICTION_CUTS), known=[shadow])
    test.jev.answers = matching(narrow=False)
    test.jev.delay = timedelta(milliseconds=100)

    outcome = await test.engine.decide(ACTION_FRICTION, card_call())

    assert (outcome.value, outcome.reason, outcome.source) == (
        CardFriction.STANDARD, DecisionReason.POLICY_OFF, DecisionSource.RULE,
    )  # fmt: skip
    assert test.rows.decisions == []
    await test.engine.drain()
    [(_, row)] = test.rows.decisions
    assert (row["shadow"], row["outcome"], row["id"]) == (True, "warning", outcome.decision_id)


async def test_a_policy_softening_the_rule_is_overruled_and_counted() -> None:
    broken = Softening()
    test = bench(stored(broken, "active", FRICTION_CUTS), known=[broken])
    test.jev.answers = matching(narrow=True)

    outcome = await test.engine.decide(ACTION_FRICTION, card_call(CardFriction.WARNING))

    assert outcome.value is CardFriction.WARNING
    assert test.sample("shosai_decision_unsafe_outcomes_total", point="action.friction") == 1
    [(_, row)] = test.rows.decisions
    assert row["outcome"] == "warning"
