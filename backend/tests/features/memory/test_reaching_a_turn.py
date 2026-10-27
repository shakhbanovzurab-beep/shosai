"""Trust, decay and what reaches a turn within its budget (Leo §7.2-§7.4, ADR 0071)."""

from datetime import timedelta
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.provenance import Provenance
from shosai.features.memory.domain.decay import EXPIRY_RETENTION, faded, half_life, retention
from shosai.features.memory.domain.facts import Fact, FactKind, FactStatus, SourceKind
from shosai.features.memory.domain.packing import (
    PROFILE_TOKENS,
    RECALL_FACTS,
    Near,
    fact_tokens,
    pack,
    profile,
    recalled,
)
from shosai.features.memory.domain.trust import label_of, taint_of
from tests.features.memory.facts_kit import NOW, fact, kinds, sources

ages = st.integers(min_value=0, max_value=3_000).map(lambda days: timedelta(days=days))
statements = st.text(min_size=1, max_size=200)


@given(source=sources, confirmed=st.booleans(), source_taint=st.sampled_from(Taint))
def test_an_unconfirmed_fact_always_raises_taint_and_a_confirmed_one_never(
    *, source: SourceKind, confirmed: bool, source_taint: Taint
) -> None:
    item = fact(source=source, confirmed=confirmed, source_taint=source_taint)
    if confirmed:
        assert taint_of(item) is Taint.NONE
    else:
        assert taint_of(item) >= max(Taint.EXTERNAL, source_taint)


def test_a_meetings_fact_is_someone_elses_speech() -> None:
    assert label_of(SourceKind.MEETING) is Provenance.MEETING_SPEECH
    assert {label_of(source) for source in SourceKind if source is not SourceKind.MEETING} == {
        Provenance.MEMORY
    }


@given(
    kind=kinds, confirmations=st.integers(0, 50), explicit=st.booleans(), first=ages, second=ages
)
def test_retention_falls_with_age_and_never_below_a_pinned_facts(
    *, kind: FactKind, confirmations: int, explicit: bool, first: timedelta, second: timedelta
) -> None:
    item = fact(kind=kind, confirmations=confirmations, explicit=explicit)
    younger, older = sorted((first, second))
    assert retention(item, NOW + older) <= retention(item, NOW + younger) <= 1.0
    assert retention(fact(kind=kind, pinned=True), NOW + older) == 1.0


def test_confirmations_and_an_explicit_request_stretch_the_half_life() -> None:
    plain = half_life(fact(kind=FactKind.GOAL))
    assert plain == timedelta(days=30)
    assert half_life(fact(kind=FactKind.GOAL, confirmations=3)) == timedelta(days=90)
    assert half_life(fact(kind=FactKind.GOAL, explicit=True)) == timedelta(days=60)


def test_a_fact_fades_below_the_expiry_level() -> None:
    goal = fact(kind=FactKind.GOAL)
    assert not faded(goal, NOW + timedelta(days=81))
    assert faded(goal, NOW + timedelta(days=83))
    assert retention(goal, NOW + timedelta(days=83)) < EXPIRY_RETENTION
    assert not faded(fact(kind=FactKind.GOAL, pinned=True), NOW + timedelta(days=9_000))


@given(st.lists(statements, max_size=30), st.integers(1, 20), st.integers(0, 900))
def test_packing_never_passes_its_budget(texts: list[str], count: int, tokens: int) -> None:
    facts = [fact(statement=text) for text in texts]
    chosen = pack(facts, count, tokens)
    assert len(chosen) <= count
    assert sum(fact_tokens(item) for item in chosen) <= tokens
    # Не поместившийся факт пропущен, а каждый следующий, что помещается, взят по порядку.
    spent, taken = 0, 0
    for item in facts:
        cost = fact_tokens(item)
        if taken < count and spent + cost <= tokens:
            assert chosen[taken].id == item.id
            spent, taken = spent + cost, taken + 1
    assert taken == len(chosen)


def test_a_long_fact_is_skipped_rather_than_ending_the_list() -> None:
    long, short = fact(statement="x" * 2_000), fact(statement="short")
    assert pack([long, short], 12, 100) == (short,)


def test_recall_keeps_current_facts_above_the_floor_most_useful_first() -> None:
    strong = fact(statement="strong")
    weak = fact(statement="weak", confidence=0.4)
    candidate = fact(statement="candidate", status=FactStatus.CANDIDATE)
    below = fact(statement="below")
    near = [Near(weak, 0.9), Near(strong, 0.8), Near(candidate, 0.99), Near(below, 0.1)]
    assert recalled(near, NOW, floor=0.3, max_tokens=600) == (strong, weak)
    many = [Near(fact(statement=f"f{n}"), 0.9) for n in range(30)]
    assert len(recalled(many, NOW, floor=0.3, max_tokens=10_000)) == RECALL_FACTS


def test_the_profile_core_takes_pins_then_preferences_listed_by_id() -> None:
    ids = [UUID(int=n) for n in range(1, 6)]
    pinned = fact(ids[3], pinned=True, kind=FactKind.GOAL)
    fresh = fact(ids[1], kind=FactKind.PREFERENCE)
    stale = fact(ids[0], kind=FactKind.PREFERENCE, last_confirmed_at=NOW - timedelta(days=900))
    other = fact(ids[2], kind=FactKind.FACT)
    gone = fact(ids[4], kind=FactKind.PREFERENCE, status=FactStatus.FORGOTTEN)
    assert profile([pinned, fresh, stale, other, gone], NOW, 600) == (stale, fresh, pinned)
    tight = fact_tokens(pinned) + fact_tokens(fresh)
    assert profile([pinned, fresh, stale], NOW, tight) == (fresh, pinned)


@given(st.lists(statements, max_size=40))
def test_the_profile_core_stays_within_its_share(texts: list[str]) -> None:
    facts: list[Fact] = [fact(statement=text, pinned=True) for text in texts]
    chosen = profile(facts, NOW, 10_000)
    assert sum(fact_tokens(item) for item in chosen) <= PROFILE_TOKENS
    assert list(chosen) == sorted(chosen, key=lambda item: item.id)
    assert profile(facts, NOW, 10_000) == chosen
