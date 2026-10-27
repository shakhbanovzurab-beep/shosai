"""A video recording's start checks and its states (MR-D4, meetings plan §3.6)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.meetings.domain.recordings import (
    ACTIVE_STATES,
    LENGTH_LIMIT,
    RecordingRefusal,
    RecordingState,
    StartFacts,
    advanced,
    over_length,
    start_refusal,
)

MAY_START = StartFacts(
    is_owner=True,
    room_open=True,
    call_live=True,
    in_plan=True,
    storage_left_bytes=1,
    room_recording=False,
    platform_active=0,
)
EVERYTHING_WRONG = StartFacts(
    is_owner=False,
    room_open=False,
    call_live=False,
    in_plan=False,
    storage_left_bytes=0,
    room_recording=True,
    platform_active=1,
)


def test_a_start_with_every_check_passed_may_start() -> None:
    assert start_refusal(MAY_START) is None


@pytest.mark.parametrize(
    ("fixed", "refusal"),
    [
        ({}, RecordingRefusal.NOT_FOUND),
        ({"is_owner": True}, RecordingRefusal.ROOM_CLOSED),
        ({"is_owner": True, "room_open": True}, RecordingRefusal.NO_LIVE_CALL),
        ({"is_owner": True, "room_open": True, "call_live": True}, RecordingRefusal.NOT_IN_PLAN),
        (
            {"is_owner": True, "room_open": True, "call_live": True, "in_plan": True},
            RecordingRefusal.STORAGE_LIMIT,
        ),
        (
            {
                "is_owner": True,
                "room_open": True,
                "call_live": True,
                "in_plan": True,
                "storage_left_bytes": 1,
            },
            RecordingRefusal.ALREADY_RECORDING,
        ),
        (
            {
                "is_owner": True,
                "room_open": True,
                "call_live": True,
                "in_plan": True,
                "storage_left_bytes": 1,
                "room_recording": False,
            },
            RecordingRefusal.PLATFORM_BUSY,
        ),
    ],
)
def test_the_checks_run_in_order(fixed: dict[str, bool | int], refusal: RecordingRefusal) -> None:
    assert start_refusal(replace(EVERYTHING_WRONG, **fixed)) is refusal  # type: ignore[arg-type]


def test_the_active_states_are_those_before_an_end() -> None:
    assert {RecordingState.STARTING, RecordingState.ACTIVE, RecordingState.ENDING} == ACTIVE_STATES


def test_a_late_earlier_report_is_ignored_and_an_end_state_is_final() -> None:
    assert advanced(RecordingState.STARTING, RecordingState.ACTIVE) is RecordingState.ACTIVE
    assert advanced(RecordingState.ENDING, RecordingState.ACTIVE) is RecordingState.ENDING
    assert advanced(RecordingState.ACTIVE, RecordingState.FAILED) is RecordingState.FAILED
    assert advanced(RecordingState.COMPLETE, RecordingState.FAILED) is RecordingState.COMPLETE
    assert advanced(RecordingState.FAILED, RecordingState.COMPLETE) is RecordingState.FAILED


@given(st.lists(st.sampled_from(RecordingState), max_size=10))
def test_any_reports_only_move_a_recording_forward(reports: list[RecordingState]) -> None:
    order = list(RecordingState)
    state = RecordingState.STARTING
    first_end: RecordingState | None = None
    for report in reports:
        after = advanced(state, report)
        assert order.index(after) >= order.index(state) or state not in ACTIVE_STATES
        if first_end is None and after not in ACTIVE_STATES:
            first_end = after
        state = after
    assert first_end is None or state is first_end


def test_a_recording_is_stopped_at_its_length_limit() -> None:
    started = datetime(2026, 10, 27, 12, tzinfo=UTC)

    assert timedelta(minutes=30) == LENGTH_LIMIT
    assert not over_length(started, started + LENGTH_LIMIT - timedelta(seconds=1))
    assert over_length(started, started + LENGTH_LIMIT)
