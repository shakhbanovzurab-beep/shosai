"""Retry pauses double up to a ceiling, are spread at random and are never instant."""

from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from whisperer.core.tasks.timing import Backoff, StreamTiming

MILLISECONDS = st.integers(min_value=1, max_value=600_000)


@given(first=MILLISECONDS, extra=MILLISECONDS, failed=st.integers(min_value=1, max_value=50))
def test_a_pause_is_half_to_all_of_the_doubled_pause_up_to_the_ceiling(
    first: int, extra: int, failed: int
) -> None:
    backoff = Backoff(
        first=timedelta(milliseconds=first), ceiling=timedelta(milliseconds=first + extra)
    )
    base = min(backoff.first * (1 << min(failed - 1, 16)), backoff.ceiling)

    pause = backoff.delay(failed)

    assert base / 2 <= pause <= base
    assert pause > timedelta(0)


def test_pauses_grow_with_each_failure() -> None:
    backoff = Backoff()

    assert backoff.delay(1) <= timedelta(seconds=5)
    assert backoff.delay(2) >= timedelta(seconds=5)
    assert backoff.delay(4) >= timedelta(seconds=20)
    assert backoff.delay(10) <= timedelta(seconds=120)


def test_pauses_of_simultaneous_failures_spread_out() -> None:
    pauses = {Backoff().delay(3) for _ in range(50)}

    assert len(pauses) > 1


def test_a_pause_follows_a_delivery() -> None:
    with pytest.raises(ValueError, match="номер выдачи"):
        Backoff().delay(0)


@pytest.mark.parametrize(
    ("first", "ceiling"),
    [(timedelta(0), timedelta(seconds=1)), (timedelta(seconds=2), timedelta(seconds=1))],
)
def test_the_first_pause_is_positive_and_within_the_ceiling(
    first: timedelta, ceiling: timedelta
) -> None:
    with pytest.raises(ValueError, match="пауза повтора"):
        Backoff(first=first, ceiling=ceiling)


def test_leases_are_renewed_well_within_their_term() -> None:
    with pytest.raises(ValueError, match="продление"):
        StreamTiming(lease=timedelta(seconds=10), renew_every=timedelta(seconds=10))


def test_a_retry_pause_fits_into_the_lease() -> None:
    with pytest.raises(ValueError, match="аренды"):
        StreamTiming(lease=timedelta(seconds=60))
