"""The sweep's verdict on an open room: the draft's cases (meetings plan §1.2, MR-D1)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from shosai.features.meetings.domain.idle import (
    IDLE_CLOSE_AFTER,
    SWEEP_EVERY,
    IdleFacts,
    SweepVerdict,
    sweep_verdict,
)

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
IDLE = IdleFacts(
    opened_at=NOW - timedelta(hours=3),
    sfu_reachable=True,
    in_sfu=False,
    call_live=False,
    last_finished_at=NOW - IDLE_CLOSE_AFTER,
    event_pending=False,
    broadcast_live=False,
)


def test_an_hour_empty_after_the_last_call_closes_the_room() -> None:
    assert sweep_verdict(IDLE, NOW) is SweepVerdict.CLOSE
    assert SWEEP_EVERY.total_seconds() == 300


@pytest.mark.parametrize(
    ("facts", "verdict"),
    [
        # SFU не прочитан — не закрывается ничего, даже давно пустая комната.
        (replace(IDLE, sfu_reachable=False, in_sfu=True), SweepVerdict.KEEP_SFU_UNREACHABLE),
        (replace(IDLE, in_sfu=True, call_live=True), SweepVerdict.KEEP_IN_USE),
        (replace(IDLE, call_live=True), SweepVerdict.FINISH_LOST_CALL),
        (
            replace(IDLE, last_finished_at=NOW - IDLE_CLOSE_AFTER + timedelta(seconds=1)),
            SweepVerdict.KEEP_RECENT,
        ),
        (replace(IDLE, event_pending=True, broadcast_live=True), SweepVerdict.KEEP_EVENT_PENDING),
        (replace(IDLE, broadcast_live=True), SweepVerdict.KEEP_BROADCAST_LIVE),
    ],
)
def test_the_guards_keep_a_room_open(facts: IdleFacts, verdict: SweepVerdict) -> None:
    assert sweep_verdict(facts, NOW) is verdict


def test_a_room_nobody_came_to_is_idle_since_it_was_opened() -> None:
    never_joined = replace(IDLE, last_finished_at=None, opened_at=NOW - timedelta(minutes=59))

    assert sweep_verdict(never_joined, NOW) is SweepVerdict.KEEP_RECENT
    assert sweep_verdict(never_joined, NOW + timedelta(minutes=1)) is SweepVerdict.CLOSE
