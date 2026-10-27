"""A call folded from webhooks: the same in any order and under replays (meetings plan §3.6)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from shosai.features.meetings.domain.calls import (
    Call,
    CallState,
    finished,
    handed_over,
    opened,
    seen,
)

T0 = datetime(2026, 10, 27, 10, tzinfo=UTC)
CALL_ID = uuid.uuid4()
ROOM_ID = uuid.uuid4()
SID = "RM_abc"


@dataclass(frozen=True, slots=True)
class Webhook:
    kind: str
    at: datetime
    participants: int | None = None


def fold(webhooks: Sequence[Webhook]) -> Call:
    call: Call | None = None
    for webhook in webhooks:
        if call is None:
            call = opened(CALL_ID, ROOM_ID, SID, webhook.at)
        if webhook.kind == "finished":
            call = finished(call, webhook.at)
        else:
            call = seen(call, webhook.at, webhook.participants)
    assert call is not None
    return call


def test_a_call_opens_live_and_ends_through_its_finish_and_handover() -> None:
    call = opened(CALL_ID, ROOM_ID, SID, T0)
    assert (call.state, call.is_live, call.seconds()) == (CallState.LIVE, True, 0)

    # Передать заметкам можно только законченный звонок.
    assert handed_over(call, T0) is call

    ending = finished(seen(call, T0 + timedelta(minutes=1), 3), T0 + timedelta(minutes=45))
    assert (ending.state, ending.peak_participants, ending.seconds()) == (CallState.ENDING, 3, 2700)
    assert finished(ending, T0 + timedelta(hours=2)) == ending

    ended = handed_over(ending, T0 + timedelta(minutes=46))
    assert (ended.state, ended.ended_at) == (CallState.ENDED, T0 + timedelta(minutes=46))
    assert handed_over(ended, T0 + timedelta(hours=3)) == ended
    assert finished(ended, T0 + timedelta(hours=3)) == ended


def test_a_finish_that_came_first_still_gives_the_earliest_start() -> None:
    call = fold([Webhook("finished", T0 + timedelta(minutes=30)), Webhook("started", T0)])

    assert (call.state, call.started_at, call.seconds()) == (CallState.ENDING, T0, 1800)


minutes = st.integers(min_value=0, max_value=600)
events = st.lists(
    st.one_of(
        st.builds(Webhook, st.just("started"), minutes.map(lambda m: T0 + timedelta(minutes=m))),
        st.builds(
            Webhook,
            st.just("participant"),
            minutes.map(lambda m: T0 + timedelta(minutes=m)),
            st.integers(min_value=0, max_value=50),
        ),
    ),
    min_size=1,
    max_size=12,
)


@given(events=events, finish=st.none() | minutes, data=st.data())
def test_any_order_and_any_replay_fold_to_the_same_call(
    events: list[Webhook], finish: int | None, data: st.DataObject
) -> None:
    webhooks = list(events)
    if finish is not None:
        webhooks.append(Webhook("finished", T0 + timedelta(minutes=finish)))
    shuffled = data.draw(st.permutations(webhooks))
    replayed = [*shuffled, *data.draw(st.lists(st.sampled_from(webhooks), max_size=6))]

    expected = fold(webhooks)
    assert fold(shuffled) == expected
    assert fold(replayed) == expected
    assert expected.started_at == min(webhook.at for webhook in webhooks)
    assert expected.peak_participants == max(
        (webhook.participants or 0 for webhook in webhooks), default=0
    )
    assert (expected.state is CallState.ENDING) == (finish is not None)
    assert expected.seconds() >= 0
