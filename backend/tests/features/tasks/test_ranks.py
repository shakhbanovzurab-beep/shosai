"""Card order by fractional keys: one key per move, the column always in order (tasks step 1)."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from shosai.features.tasks.domain.ranks import (
    DIGITS,
    REBALANCE_LENGTH,
    ZERO,
    RankError,
    needs_rebalance,
    rank_at,
    rank_between,
    spaced_ranks,
)


def valid(key: str) -> bool:
    return bool(key) and not key.endswith(ZERO) and all(char in DIGITS for char in key)


operations = st.lists(
    st.tuples(
        st.sampled_from(["insert", "move"]),
        st.integers(min_value=-2, max_value=60),
        st.integers(min_value=0, max_value=10_000),
    ),
    max_size=300,
)


@settings(max_examples=200)
@given(operations)
def test_inserts_and_moves_keep_a_strict_order_and_write_one_key_each(
    ops: list[tuple[str, int, int]],
) -> None:
    order: list[int] = []  # Карточки колонки в том порядке, в каком их поставил человек.
    keys: dict[int, str] = {}
    next_card = 0
    for kind, position, pick in ops:
        if kind == "move" and order:
            card = order.pop(pick % len(order))
        else:
            card, next_card = next_card, next_card + 1
        others = [keys[other] for other in order]
        before = dict(keys)
        key = rank_at(others, position)
        order.insert(min(max(position, 0), len(order)), card)
        keys[card] = key

        assert valid(key)
        # Пишется один ключ — переставленной карточки; он может совпасть с прежним.
        assert {c for c in keys if keys[c] != before.get(c)} <= {card}
        if needs_rebalance(key):
            keys = dict(zip(order, spaced_ranks(len(order)), strict=True))
        assert sorted(order, key=keys.__getitem__) == order
        assert len(set(keys.values())) == len(keys)


@given(st.integers(min_value=0, max_value=5_000))
def test_spaced_keys_are_short_valid_and_in_order(count: int) -> None:
    keys = spaced_ranks(count)

    assert len(keys) == count
    assert all(valid(key) for key in keys)
    assert list(keys) == sorted(set(keys))
    assert all(len(key) <= 3 for key in keys)


@given(st.lists(st.integers(min_value=0, max_value=1), max_size=400))
def test_keys_squeezed_at_one_spot_stay_valid_until_rebalanced(sides: list[int]) -> None:
    low, high = "V", "W"
    for side in sides:
        key = rank_between(low, high)
        assert low < key < high
        assert valid(key)
        if side:
            low = key
        else:
            high = key
        if needs_rebalance(key):
            assert len(key) > REBALANCE_LENGTH
            break


def test_the_ends_of_a_column() -> None:
    assert rank_between(None, None) == "V"
    assert rank_between(None, "1") == "0V"
    assert rank_between("z", None) == "zV"
    assert rank_between("a", "a1") == "a0V"
    assert rank_at([], 5) == "V"


@pytest.mark.parametrize(
    ("before", "after"),
    [("b", "a"), ("a", "a"), ("a0", None), (None, ""), ("a!", None)],
)
def test_keys_out_of_order_or_malformed_are_a_programming_error(
    before: str | None, after: str | None
) -> None:
    with pytest.raises(RankError):
        rank_between(before, after)


def test_a_negative_count_of_keys_is_refused() -> None:
    with pytest.raises(RankError):
        spaced_ranks(-1)
