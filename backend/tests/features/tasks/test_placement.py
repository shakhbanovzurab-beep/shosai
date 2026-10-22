"""Where a card shows and what lands on the incoming board (tasks plan §3.5, TK-D4, TK-D5)."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.tasks.domain.placement import (
    BoardColumn,
    IncomingFacts,
    comes_to,
    first_column_of,
    shown_on_board,
    spot_for,
    status_after_move,
)
from shosai.features.tasks.domain.tasks import TaskSource, TaskStatus

NOW = datetime(2026, 10, 22, 9, tzinfo=UTC)
statuses = st.sampled_from(list(TaskStatus))


@st.composite
def boards(draw: st.DrawFn) -> list[BoardColumn]:
    """A board's columns in any order and positions, with every kind at least once."""
    kinds = list(TaskStatus) + draw(st.lists(statuses, max_size=17))
    positions = draw(st.permutations(range(len(kinds))))
    return [
        BoardColumn(uuid.uuid4(), kind, position)
        for kind, position in zip(kinds, positions, strict=True)
    ]


@given(boards(), statuses, st.data())
def test_a_card_always_shows_in_a_column_of_its_status(
    columns: list[BoardColumn], status: TaskStatus, data: st.DataObject
) -> None:
    current = data.draw(st.none() | st.sampled_from([column.column_id for column in columns]))
    spot = spot_for(status, columns, current)
    by_id = {column.column_id: column for column in columns}

    assert by_id[spot.column_id].kind is status
    sitting = by_id.get(current) if current is not None else None
    if sitting is not None and sitting.kind is status:
        assert spot.column_id == current
        assert not spot.to_top
    else:
        assert spot.to_top
        assert by_id[spot.column_id] == first_column_of(columns, status)


@given(statuses, statuses)
def test_a_move_gives_the_task_its_column_kind(status: TaskStatus, kind: TaskStatus) -> None:
    assert status_after_move(status, kind) is kind


def test_a_board_without_a_column_of_the_status_is_a_programming_error() -> None:
    columns = [BoardColumn(uuid.uuid4(), TaskStatus.TODO, 0)]

    with pytest.raises(ValueError, match="колонки"):
        spot_for(TaskStatus.DONE, columns, None)


def test_a_board_shows_open_cards_and_those_done_in_the_last_thirty_days() -> None:
    assert shown_on_board(TaskStatus.TODO, None, NOW)
    assert shown_on_board(TaskStatus.DONE, NOW - timedelta(days=30), NOW)
    assert not shown_on_board(TaskStatus.DONE, NOW - timedelta(days=30, seconds=1), NOW)
    assert not shown_on_board(TaskStatus.DONE, None, NOW)


def test_what_comes_to_a_person() -> None:
    me, colleague, org = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    mine = IncomingFacts(TaskStatus.TODO, me, None, None, TaskSource.MEETING)
    shared = replace(mine, org_id=org)

    assert comes_to(me, mine)
    assert not comes_to(me, replace(mine, source=TaskSource.MANUAL))
    assert not comes_to(me, replace(mine, status=TaskStatus.DONE))
    assert not comes_to(colleague, mine)
    assert comes_to(me, replace(shared, user_id=colleague, assignee_user_id=me))
    assert not comes_to(me, replace(shared, assignee_user_id=colleague))
    assert not comes_to(me, shared)
