"""The policies: never less careful than the rule — voice.approval, which reads consent, aside —
unsure on the careful side, valid questions, bounded states, records without text (ADR 0026
point 3, ADR 0069)."""

from collections.abc import Mapping
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.agent_tools.spec import Reversibility
from shosai.core.ai.decisions import DecisionRequest
from shosai.features.decisions.domain.policies import POLICIES, policies_by_key, policy_wording
from shosai.features.decisions.domain.policies.action_friction import (
    ACTION_FRICTION,
    CardFacts,
    CardFriction,
)
from shosai.features.decisions.domain.policies.content_injection import (
    CONTENT_INJECTION,
    InjectionFinding,
    TextFacts,
)
from shosai.features.decisions.domain.policies.turn_route import (
    MAX_CANDIDATES,
    TURN_ROUTE,
    ToolsetCandidate,
    TurnFacts,
)
from shosai.features.decisions.domain.policies.voice_approval import (
    VOICE_APPROVAL,
    VoiceConsent,
    VoiceFacts,
)
from shosai.features.decisions.domain.policy import Policy, check_point
from shosai.features.decisions.domain.state import state_tokens
from shosai.features.decisions.domain.verdicts import Verdict

verdicts = st.sampled_from(Verdict)
words = st.text(max_size=4_000)
toolsets = st.from_regex(r"[a-z][a-z0-9_]{0,12}", fullmatch=True)
cards = st.builds(
    CardFacts,
    tool=st.just("tasks.create"),
    toolset=st.just("tasks"),
    reversibility=st.sampled_from(Reversibility),
    items=st.integers(min_value=1, max_value=20),
    other_space=st.booleans(),
    rounds=st.integers(min_value=1, max_value=10),
    request=words,
    card=words,
)
pieces = st.builds(
    TextFacts,
    label=st.sampled_from(["web", "file:own", "mcp:Acme"]),
    tool=st.just("web.search"),
    text=words,
)
voices = st.builds(VoiceFacts, read_back=words, utterance=st.text(max_size=600))
turns = st.builds(
    TurnFacts,
    question=words,
    previous=words,
    section=st.text(max_size=80),
    candidates=st.lists(toolsets, max_size=20, unique=True).map(
        lambda names: tuple(ToolsetCandidate(name, f"Tools of {name}.") for name in names)
    ),
    forced=st.integers(min_value=1, max_value=5),
    room=st.integers(min_value=0, max_value=4_000),
    turn=st.integers(min_value=0, max_value=200),
)


def card(tool: str, reversibility: Reversibility) -> CardFacts:
    """A one-item write in the thread's own space, asked for in one round."""
    toolset = tool.split(".", 1)[0]
    return CardFacts(
        tool=tool, toolset=toolset, reversibility=reversibility, items=1, other_space=False,
        rounds=1, request="q", card="c",
    )  # fmt: skip


def policy_of(facts: object) -> Policy[Any, Any]:
    """The policy whose facts these are."""
    by_type: dict[type, Policy[Any, Any]] = {
        TurnFacts: TURN_ROUTE,
        CardFacts: ACTION_FRICTION,
        TextFacts: CONTENT_INJECTION,
        VoiceFacts: VOICE_APPROVAL,
    }
    return by_type[type(facts)]


def judged(policy: Policy[Any, Any], facts: object, data: st.DataObject) -> Mapping[str, Verdict]:
    """A verdict for each of the policy's questions."""
    return {name: data.draw(verdicts) for name in policy.signals(facts)}


@given(cards, st.sampled_from(CardFriction), st.data())
def test_friction_never_lightens_the_rules_card(
    facts: CardFacts, rule: CardFriction, data: st.DataObject
) -> None:
    outcome = ACTION_FRICTION.outcome(facts, judged(ACTION_FRICTION, facts, data), {})
    final = ACTION_FRICTION.careful(rule, outcome)
    assert final >= rule
    assert not ACTION_FRICTION.less_careful(final, rule)


@given(pieces, st.sampled_from(InjectionFinding), st.data())
def test_a_suspicious_run_stays_suspicious(
    facts: TextFacts, rule: InjectionFinding, data: st.DataObject
) -> None:
    outcome = CONTENT_INJECTION.outcome(facts, judged(CONTENT_INJECTION, facts, data), {})
    final = CONTENT_INJECTION.careful(rule, outcome)
    assert final >= rule
    assert not CONTENT_INJECTION.less_careful(final, rule)


@given(voices, st.data())
def test_only_a_sure_yes_gives_consent_and_only_this_policy_reads_one(
    facts: VoiceFacts, data: st.DataObject
) -> None:
    given_verdicts = judged(VOICE_APPROVAL, facts, data)
    outcome = VOICE_APPROVAL.outcome(facts, given_verdicts, {})
    assert (outcome is VoiceConsent.GIVEN) == (given_verdicts["approves"] is Verdict.YES)
    assert VOICE_APPROVAL.careful(VoiceConsent.NOT_GIVEN, outcome) is outcome
    assert [policy.key for policy in POLICIES if policy.reads_consent] == ["voice.approval@1"]
    assert VOICE_APPROVAL.settled(facts, VoiceConsent.NOT_GIVEN) is (not facts.utterance.strip())


@pytest.mark.parametrize("policy", POLICIES, ids=lambda policy: policy.key)
def test_an_unsure_verdict_is_read_as_its_aims_say(policy: Policy[Any, Any]) -> None:
    facts = {
        "turn.route": TurnFacts("q", "", "", (ToolsetCandidate("notes", "Notes."),), 1, 900, 1),
        "action.friction": card("tasks.create", Reversibility.REVERSIBLE),
        "content.injection": TextFacts("web", "web.search", "text"),
        "voice.approval": VoiceFacts("Create a task\nTitle: Call Anna", "yes, go ahead"),
    }[policy.point]
    signals = policy.signals(facts)
    assert {signal.cut for signal in signals.values()} == set(policy.cuts) == set(policy.aims.cuts)
    for name, signal in signals.items():
        joined = policy.aims.cuts[signal.cut].unsure_joins
        for other in (Verdict.YES, Verdict.NO):
            rest = {key: other for key in signals if key != name}
            chances = dict.fromkeys(signals, 0.9)
            unsure = policy.outcome(facts, {**rest, name: Verdict.UNSURE}, chances)
            assert unsure == policy.outcome(facts, {**rest, name: joined}, chances)


def test_a_card_is_standard_only_when_it_surely_matches_and_stays_narrow() -> None:
    facts = card("tasks.create", Reversibility.REVERSIBLE)
    sure = {"matches_request": Verdict.YES, "reach": Verdict.NO}
    assert ACTION_FRICTION.outcome(facts, sure, {}) is CardFriction.STANDARD
    for name, verdict in (("matches_request", Verdict.UNSURE), ("reach", Verdict.YES)):
        assert ACTION_FRICTION.outcome(facts, {**sure, name: verdict}, {}) is CardFriction.WARNING


def test_friction_is_not_asked_once_the_rule_warns_or_the_write_cannot_be_undone() -> None:
    facts = card("files.delete", Reversibility.REVERSIBLE)
    assert ACTION_FRICTION.settled(facts, CardFriction.WARNING)
    assert not ACTION_FRICTION.settled(facts, CardFriction.STANDARD)
    gone = card("files.delete", Reversibility.IRREVERSIBLE)
    assert ACTION_FRICTION.settled(gone, CardFriction.STANDARD)


@given(turns, st.data())
def test_a_ranking_holds_only_surely_needed_candidates(
    facts: TurnFacts, data: st.DataObject
) -> None:
    given_verdicts = judged(TURN_ROUTE, facts, data)
    chances = {name: data.draw(st.floats(min_value=0, max_value=1)) for name in given_verdicts}
    ranking = TURN_ROUTE.outcome(facts, given_verdicts, chances)
    names = [candidate.name for candidate in facts.candidates[:MAX_CANDIDATES]]
    assert len(set(ranking)) == len(ranking)
    assert all(given_verdicts[f"needs_{name}"] is Verdict.YES for name in ranking)
    assert set(ranking) == {n for n in names if given_verdicts[f"needs_{n}"] is Verdict.YES}
    ranked = [chances[f"needs_{name}"] for name in ranking]
    assert ranked == sorted(ranked, reverse=True)
    assert TURN_ROUTE.settled(facts, ()) is (not facts.candidates)


@given(st.one_of(turns, cards, pieces, voices))
def test_every_policy_asks_a_valid_request_within_its_budget(facts: object) -> None:
    policy = policy_of(facts)
    questions = policy.questions(facts)
    state = policy.state(facts)
    assert state_tokens(state) <= policy.budget
    assert len(questions) <= MAX_CANDIDATES
    if questions:
        DecisionRequest(state=state, questions=questions)
    assert set(policy.signals(facts)) == set(questions)


@given(st.one_of(turns, cards, pieces, voices))
def test_a_record_keeps_no_text(facts: object) -> None:
    policy = policy_of(facts)
    for name, value in policy.facts(facts).items():
        assert isinstance(value, bool | int | float | str), name
        if isinstance(value, str):
            assert len(value) <= 40, name
            assert value.replace(".", "").replace("_", "").replace(":", "").isalnum(), name


def test_an_mcp_servers_name_never_reaches_a_record() -> None:
    kept = CONTENT_INJECTION.facts(TextFacts("mcp:Acme CRM", "mcp.acme.read", "hello"))
    assert kept == {"label": "mcp", "tool": "mcp", "length": "short"}


def test_policies_are_named_once_and_their_wording_hashes_apart() -> None:
    found = policies_by_key()
    assert set(found) == {
        "turn.route@1", "action.friction@1", "content.injection@1", "voice.approval@1",
    }  # fmt: skip
    assert len({policy.digest() for policy in POLICIES}) == len(POLICIES)
    assert set(policy_wording()) == set(found)
    assert TURN_ROUTE.digest() == TURN_ROUTE.digest()


@pytest.mark.parametrize("name", ["turn", "Turn.Route", "turn.route.x", "turn.1route"])
def test_a_malformed_point_is_refused(name: str) -> None:
    with pytest.raises(ValueError, match="точки решения"):
        check_point(name)


def test_a_toolset_name_outside_the_wire_form_is_refused() -> None:
    with pytest.raises(ValueError, match="набора"):
        ToolsetCandidate("Notes!", "x")
