"""Boards, columns, templates and the layout rule (tasks plan §3.3, TK-D5)."""

import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.tasks.domain.boards import (
    BOARD_NAME_MAX,
    TEMPLATES,
    BoardRule,
    BoardRuleError,
    LayoutColumn,
    ShownColumn,
    check_board_room,
    check_card_room,
    check_column_room,
    check_kinds_kept,
    checked_board_name,
    checked_column_title,
    checked_layout,
)
from shosai.features.tasks.domain.tasks import TaskStatus


def rule_of(error: pytest.ExceptionInfo[BoardRuleError]) -> BoardRule:
    return error.value.rule


def test_every_template_brings_a_column_of_each_kind() -> None:
    for columns in TEMPLATES.values():
        check_kinds_kept([kind for _, kind in columns])
    assert [name.value for name, _ in TEMPLATES[next(iter(TEMPLATES))]] == [
        "todo",
        "in_progress",
        "done",
    ]


@pytest.mark.parametrize(
    ("raw", "rule"),
    [("   ", BoardRule.NAME_REQUIRED), ("x" * (BOARD_NAME_MAX + 1), BoardRule.NAME_TOO_LONG)],
)
def test_a_board_name_is_trimmed_and_bounded(raw: str, rule: BoardRule) -> None:
    assert checked_board_name("  Работа  ") == "Работа"
    with pytest.raises(BoardRuleError) as error:
        checked_board_name(raw)
    assert rule_of(error) is rule


def test_a_column_title_is_trimmed_and_bounded() -> None:
    assert checked_column_title(" QA ") == "QA"
    with pytest.raises(BoardRuleError) as error:
        checked_column_title("")
    assert error.value.code == "title_required"


@pytest.mark.parametrize(
    ("check", "count", "code"),
    [
        (check_board_room, 50, "boards_full"),
        (check_column_room, 20, "board_columns_full"),
        (check_card_room, 1_000, "board_full"),
    ],
)
def test_the_bounds_of_a_board(check: object, count: int, code: str) -> None:
    assert callable(check)
    check(count - 1)
    with pytest.raises(BoardRuleError) as error:
        check(count)
    assert error.value.code == code


def test_a_board_keeps_a_column_of_each_kind() -> None:
    with pytest.raises(BoardRuleError) as error:
        check_kinds_kept([TaskStatus.TODO, TaskStatus.DONE])
    assert error.value.code == "last_column_of_kind"


@st.composite
def boards_and_layouts(draw: st.DrawFn) -> tuple[list[ShownColumn], list[LayoutColumn]]:
    """A board as shown and a layout that only reorders its columns and their cards."""
    shown = [
        ShownColumn(uuid.uuid4(), tuple(uuid.uuid4() for _ in range(draw(st.integers(0, 6)))))
        for _ in range(draw(st.integers(1, 6)))
    ]
    layout = [
        LayoutColumn(
            column.column_id, f"Колонка {index}", tuple(draw(st.permutations(column.card_ids)))
        )
        for index, column in enumerate(draw(st.permutations(shown)))
    ]
    return shown, layout


@given(boards_and_layouts())
def test_a_layout_that_only_reorders_passes(
    board: tuple[list[ShownColumn], list[LayoutColumn]],
) -> None:
    shown, layout = board

    assert checked_layout(shown, layout) == tuple(layout)


@given(boards_and_layouts(), st.integers(0, 3))
def test_a_layout_of_another_board_state_is_board_changed(
    board: tuple[list[ShownColumn], list[LayoutColumn]], how: int
) -> None:
    shown, layout = board
    first = layout[0]
    if how == 0:
        changed = layout[1:] if len(layout) > 1 else [*layout, LayoutColumn(uuid.uuid4(), "X", ())]
    elif how == 1:
        changed = [
            LayoutColumn(first.column_id, first.title, (*first.task_ids, uuid.uuid4())),
            *layout[1:],
        ]
    elif how == 2:
        changed = [*layout, layout[0]]
    else:
        changed = [
            LayoutColumn(first.column_id, first.title, (*first.task_ids, *first.task_ids[:1])),
            *layout[1:],
        ]
    if changed == layout:
        return

    with pytest.raises(BoardRuleError) as error:
        checked_layout(shown, changed)
    assert error.value.code == "board_changed"


def test_a_card_moved_between_columns_by_a_layout_is_board_changed() -> None:
    card = uuid.uuid4()
    left, right = ShownColumn(uuid.uuid4(), (card,)), ShownColumn(uuid.uuid4(), ())
    layout = [LayoutColumn(left.column_id, "A", ()), LayoutColumn(right.column_id, "B", (card,))]

    with pytest.raises(BoardRuleError) as error:
        checked_layout([left, right], layout)
    assert error.value.code == "board_changed"


def test_a_layout_checks_its_titles() -> None:
    column = ShownColumn(uuid.uuid4(), ())

    assert checked_layout([column], [LayoutColumn(column.column_id, "  Готово ", ())])[0].title == (
        "Готово"
    )
    with pytest.raises(BoardRuleError) as error:
        checked_layout([column], [LayoutColumn(column.column_id, " ", ())])
    assert error.value.code == "title_required"
