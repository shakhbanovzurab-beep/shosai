"""A run's stream: monotonic numbers, steps in order, one terminal event (ADR 0032)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.agent.domain.stream import (
    TERMINAL,
    EventKind,
    StreamClosedError,
    StreamLedger,
)

STEP_KINDS = (EventKind.STEP_STARTED, EventKind.STEP_COMPLETED, EventKind.STEP_FAILED)
OTHER_KINDS = [kind for kind in EventKind if kind not in STEP_KINDS]


@given(st.lists(st.sampled_from(OTHER_KINDS), max_size=40))
def test_numbers_rise_by_one_and_nothing_follows_the_end(kinds: list[EventKind]) -> None:
    ledger = StreamLedger()
    seen: list[int] = []
    terminal_count = 0
    for kind in kinds:
        if ledger.ended:
            with pytest.raises(StreamClosedError):
                ledger.emit(kind, {})
            continue
        ledger, event = ledger.emit(kind, {})
        seen.append(event.seq)
        terminal_count += kind in TERMINAL

    assert seen == list(range(1, len(seen) + 1))
    assert terminal_count <= 1


def test_a_step_opens_once_and_closes_once() -> None:
    ledger, _ = StreamLedger().emit(EventKind.STEP_STARTED, {"id": "s1", "activity": "think"})

    with pytest.raises(StreamClosedError, match="уже открыт"):
        ledger.emit(EventKind.STEP_STARTED, {"id": "s1"})
    ledger, _ = ledger.emit(EventKind.STEP_COMPLETED, {"id": "s1"})
    with pytest.raises(StreamClosedError, match="не открыт"):
        ledger.emit(EventKind.STEP_FAILED, {"id": "s1"})
    with pytest.raises(StreamClosedError, match="id"):
        ledger.emit(EventKind.STEP_STARTED, {"activity": "think"})


def test_a_pause_is_not_an_end_and_the_end_closes_open_steps() -> None:
    ledger, _ = StreamLedger().emit(EventKind.STEP_STARTED, {"id": "s1"})
    ledger, _ = ledger.emit(EventKind.RUN_PAUSED, {"action_id": "a"})

    assert not ledger.ended
    ledger, event = ledger.emit(EventKind.RUN_COMPLETED, {"outcome": "answered"})
    assert (ledger.ended, ledger.open_steps, event.seq) == (True, frozenset(), 3)
