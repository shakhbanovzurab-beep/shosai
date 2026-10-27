"""A fact's changes: accept, pin, forget, supersede and restore (Leo §7.2, ADR 0071)."""

from datetime import timedelta
from itertools import pairwise
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.memory.domain.facts import (
    EndReason,
    FactStatus,
    MemoryRule,
    MemoryRuleError,
    MemorySource,
    accept,
    clean_statement,
    confirmed_on_write,
    forget,
    pin,
    restore,
    supersede,
)
from tests.features.memory.facts_kit import NOW, fact

LATER = NOW + timedelta(hours=1)


def test_a_statement_is_one_clean_line_within_its_limit() -> None:
    assert clean_statement("  Prefers\n short\tanswers \x00 ") == "Prefers short answers"
    for text in ("", " \n\t", "x" * 501):
        with pytest.raises(MemoryRuleError) as refused:
            clean_statement(text)
        assert refused.value.rule is MemoryRule.INVALID
    assert clean_statement("x" * 300, limit=300) == "x" * 300


def test_accepting_makes_a_candidate_the_persons_own() -> None:
    candidate = fact(status=FactStatus.CANDIDATE)
    accepted = accept(candidate, LATER)
    assert (accepted.status, accepted.confirmed, accepted.last_confirmed_at) == (
        FactStatus.ACTIVE,
        True,
        LATER,
    )
    with pytest.raises(MemoryRuleError) as refused:
        accept(accepted, LATER)
    assert refused.value.rule is MemoryRule.NOT_CANDIDATE


def test_pinning_confirms_and_unpinning_only_unpins() -> None:
    pinned = pin(fact(), pinned=True, now=LATER)
    assert (pinned.pinned, pinned.confirmed, pinned.confirmations) == (True, True, 1)
    unpinned = pin(pinned, pinned=False, now=LATER + timedelta(hours=1))
    assert not unpinned.pinned
    assert unpinned.last_confirmed_at == LATER
    with pytest.raises(MemoryRuleError):
        pin(fact(status=FactStatus.CANDIDATE), pinned=True, now=LATER)


def test_forgetting_a_candidate_is_turning_it_down() -> None:
    turned_down = forget(fact(status=FactStatus.CANDIDATE), EndReason.FORGOT, LATER)
    assert (turned_down.status, turned_down.ended_reason) == (
        FactStatus.FORGOTTEN,
        EndReason.TURNED_DOWN,
    )
    forgotten = forget(fact(pinned=True), EndReason.FORGOT, LATER)
    assert (forgotten.ended_reason, forgotten.pinned) == (EndReason.FORGOT, False)
    with pytest.raises(MemoryRuleError):
        forget(forgotten, EndReason.FORGOT, LATER)


@given(st.lists(st.text(alphabet="abc ", min_size=1, max_size=8), min_size=1, max_size=12))
def test_a_chain_of_edits_leaves_one_current_fact(edits: list[str]) -> None:
    facts = [fact(pinned=True)]
    for text in edits:
        successor = fact(statement=text, source=MemorySource.USER_EDIT)
        closed, opened = supersede(facts[-1], successor, LATER)
        facts[-1] = closed
        facts.append(opened)
    assert [item.current for item in facts].count(True) == 1
    assert facts[-1].pinned
    assert all(item.superseded_by == nxt.id for item, nxt in pairwise(facts))


def test_restoring_brings_a_forgotten_fact_back_within_a_day() -> None:
    forgotten = forget(fact(), EndReason.FORGOT, NOW)
    back, successor = restore(forgotten, None, NOW + timedelta(hours=23))
    assert back.current
    assert successor is None
    with pytest.raises(MemoryRuleError) as late:
        restore(forgotten, None, NOW + timedelta(hours=25))
    assert late.value.rule is MemoryRule.RESTORE_CLOSED
    with pytest.raises(MemoryRuleError):
        restore(forget(fact(), EndReason.EXPIRED, NOW), None, LATER)


def test_restoring_a_superseded_fact_ends_its_successor() -> None:
    closed, opened = supersede(fact(pinned=True), fact(), NOW)
    back, ended = restore(closed, opened, LATER)
    assert back.current
    assert back.pinned
    assert ended is not None
    assert ended.status is FactStatus.FORGOTTEN
    with pytest.raises(MemoryRuleError):
        restore(closed, fact(), LATER)
    with pytest.raises(MemoryRuleError):
        restore(closed, opened, NOW + timedelta(days=2))


def test_a_supersession_needs_a_new_active_fact() -> None:
    old = fact()
    with pytest.raises(MemoryRuleError):
        supersede(old, old, NOW)
    with pytest.raises(MemoryRuleError):
        supersede(old, fact(status=FactStatus.CANDIDATE), NOW)
    with pytest.raises(MemoryRuleError):
        supersede(forget(old, EndReason.FORGOT, NOW), fact(id=uuid4()), NOW)


@pytest.mark.parametrize(
    ("source", "explicit", "confirmed"),
    [
        (MemorySource.USER_EDIT, False, True),
        (MemorySource.SETTINGS, False, True),
        (MemorySource.USER_STATEMENT, True, True),
        (MemorySource.TEAM_CHAT, True, True),
        (MemorySource.USER_STATEMENT, False, False),
        (MemorySource.MEETING, True, False),
        (MemorySource.IMPORTED, True, False),
    ],
)
def test_only_the_persons_own_act_confirms_a_new_fact(
    source: MemorySource, *, explicit: bool, confirmed: bool
) -> None:
    assert confirmed_on_write(source, explicit=explicit) is confirmed


def test_a_turned_down_candidate_comes_back_waiting_and_forgetting_everything_is_final() -> None:
    turned_down = forget(fact(status=FactStatus.CANDIDATE), EndReason.FORGOT, NOW)
    back, _ = restore(turned_down, None, LATER)
    assert turned_down.ended_reason is EndReason.TURNED_DOWN
    assert back.pending
    with pytest.raises(MemoryRuleError):
        restore(forget(fact(), EndReason.FORGOT_ALL, NOW), None, LATER)


def test_a_replacement_replaced_again_closes_the_way_back() -> None:
    closed, opened = supersede(fact(), fact(), NOW)
    replaced, _ = supersede(opened, fact(), NOW)
    with pytest.raises(MemoryRuleError):
        restore(closed, replaced, LATER)
