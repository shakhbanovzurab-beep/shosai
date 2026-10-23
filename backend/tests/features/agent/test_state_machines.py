"""A run and an action change state only by their machines, and an end is final (Leo §5.1, §8.4)."""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.agent.domain import actions, runs
from shosai.features.agent.domain.actions import (
    ActionEvent,
    ActionStatus,
    ActionTransitionError,
    ItemOutcome,
    ProposalOrigin,
    PublicStatus,
    approvable,
    expires_at,
    finishing_event,
    item_key,
    public_status,
    transition,
)
from shosai.features.agent.domain.runs import RunEvent, RunStatus, RunTransitionError, next_status

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


@given(st.lists(st.sampled_from(RunEvent), max_size=30))
def test_no_event_leaves_an_ended_run(events: list[RunEvent]) -> None:
    status = RunStatus.RUNNING
    for event in events:
        try:
            after = next_status(status, event)
        except RunTransitionError:
            continue
        assert status not in runs.TERMINAL
        status = after


def test_a_paused_run_resumes_or_closes_but_never_fails_unseen() -> None:
    assert next_status(RunStatus.PAUSED, RunEvent.RESUME) is RunStatus.RUNNING
    assert next_status(RunStatus.PAUSED, RunEvent.CLOSE) is RunStatus.COMPLETED
    with pytest.raises(RunTransitionError):
        next_status(RunStatus.PAUSED, RunEvent.COMPLETE)


@given(st.lists(st.sampled_from(ActionEvent), max_size=30))
def test_no_event_leaves_an_ended_action(events: list[ActionEvent]) -> None:
    status = ActionStatus.PROPOSED
    for event in events:
        try:
            step = transition(status, event)
        except ActionTransitionError:
            continue
        assert step.expected is status
        assert status not in actions.TERMINAL
        status = step.to


@given(st.lists(st.sampled_from([ActionEvent.APPROVE, ActionEvent.REJECT, ActionEvent.EXPIRE])))
def test_concurrent_decisions_on_one_card_have_exactly_one_winner(
    attempts: list[ActionEvent],
) -> None:
    stored = ActionStatus.PROPOSED
    winners = 0
    for event in attempts:
        # Каждая попытка — условное обновление «WHERE status = ожидаемый», как в хранилище.
        step = transition(ActionStatus.PROPOSED, event)
        if stored is step.expected:
            stored = step.to
            winners += 1

    assert winners == min(len(attempts), 1)


@given(st.lists(st.sampled_from(list(ItemOutcome)[1:]), min_size=1, max_size=20))
def test_items_end_the_action_honestly(outcomes: list[ItemOutcome]) -> None:
    event = finishing_event(outcomes)

    if ItemOutcome.OUTCOME_UNKNOWN in outcomes:
        assert event is ActionEvent.LOSE
    elif all(outcome is ItemOutcome.SUCCEEDED for outcome in outcomes):
        assert event is ActionEvent.SUCCEED
    elif ItemOutcome.SUCCEEDED in outcomes:
        assert event is ActionEvent.SUCCEED_PARTLY
    else:
        assert event is ActionEvent.FAIL


def test_an_action_does_not_end_while_an_item_is_pending() -> None:
    with pytest.raises(ActionTransitionError):
        finishing_event([ItemOutcome.SUCCEEDED, ItemOutcome.PENDING])
    with pytest.raises(ActionTransitionError):
        finishing_event([])


def test_a_lost_execution_is_never_retried() -> None:
    lost = transition(ActionStatus.EXECUTING, ActionEvent.LOSE).to

    assert lost is ActionStatus.OUTCOME_UNKNOWN
    assert lost in actions.TERMINAL
    for event in ActionEvent:
        with pytest.raises(ActionTransitionError):
            transition(lost, event)


def test_a_card_expires_after_an_hour() -> None:
    expiry = expires_at(NOW, ProposalOrigin.TURN)

    assert expiry == NOW + timedelta(hours=1)
    assert approvable(ActionStatus.PROPOSED, expiry, NOW + timedelta(minutes=59))
    assert not approvable(ActionStatus.PROPOSED, expiry, expiry)
    assert not approvable(ActionStatus.APPROVED, expiry, NOW)


def test_the_card_shows_approved_as_executing_and_superseded_as_expired() -> None:
    assert public_status(ActionStatus.APPROVED) is PublicStatus.EXECUTING
    assert public_status(ActionStatus.SUPERSEDED) is PublicStatus.EXPIRED
    assert public_status(ActionStatus.OUTCOME_UNKNOWN) is PublicStatus.OUTCOME_UNKNOWN


def test_an_item_key_is_the_action_and_its_place() -> None:
    assert item_key("a-1", 0) == "a-1:0"
    with pytest.raises(ValueError, match="пункт"):
        item_key("a-1", 20)
