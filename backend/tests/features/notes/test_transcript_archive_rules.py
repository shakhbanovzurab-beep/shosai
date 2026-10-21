"""The transcript archive's rules: which months are due, the lines' form and their pages."""

import uuid
from datetime import UTC, date, datetime, timedelta, timezone

from hypothesis import given
from hypothesis import strategies as st

from shosai.features.notes.domain.transcript_archive import (
    ArchivedLine,
    archive_due,
    archive_key,
    decode_lines,
    encode_lines,
    last_month_due,
    lines_digest,
    page_after,
    spoken_order,
)

MOSCOW = timezone(timedelta(hours=3))
STARTED = datetime(2025, 9, 30, 23, 59, tzinfo=UTC)

lines_of = st.lists(
    st.builds(
        ArchivedLine,
        seq=st.integers(min_value=1, max_value=10_000),
        started_at=st.datetimes(timezones=st.just(UTC)),
        start_ms=st.integers(min_value=0, max_value=21_600_000),
        duration_ms=st.integers(min_value=0, max_value=60_000),
        speaker_idx=st.none() | st.integers(min_value=0, max_value=31),
        text=st.text(),
        origin=st.sampled_from(["live", "recording"]),
        run_id=st.none() | st.uuids(),
        created_at=st.datetimes(timezones=st.just(UTC)),
    ),
    unique_by=lambda line: line.seq,
    max_size=40,
)


def line(seq: int, start_ms: int) -> ArchivedLine:
    """A line said at `start_ms`."""
    return ArchivedLine(
        seq=seq, started_at=STARTED, start_ms=start_ms, duration_ms=500, speaker_idx=0,
        text=f"Line {seq}.", origin="live", run_id=None, created_at=STARTED,
    )  # fmt: skip


def test_a_month_is_due_once_it_ended_twelve_months_ago_in_utc() -> None:
    assert last_month_due(datetime(2026, 10, 21, 12, tzinfo=UTC)) == date(2025, 9, 1)
    assert last_month_due(datetime(2026, 1, 5, tzinfo=UTC)) == date(2024, 12, 1)
    # В Москве уже ноябрь, по UTC ещё октябрь: месяцы партиций — UTC.
    assert last_month_due(datetime(2026, 11, 1, 1, tzinfo=MOSCOW)) == date(2025, 9, 1)
    assert archive_due(STARTED, datetime(2026, 10, 1, tzinfo=UTC))
    assert not archive_due(STARTED, datetime(2026, 9, 30, 23, 59, 59, tzinfo=UTC))
    assert not archive_due(STARTED + timedelta(minutes=1), datetime(2026, 10, 1, tzinfo=UTC))


def test_the_archive_lives_outside_the_expiring_prefix() -> None:
    meeting_id = uuid.uuid4()

    assert archive_key(meeting_id) == f"archive/transcripts/{meeting_id}.jsonl.gz"
    assert not archive_key(meeting_id).startswith("transient/")


@given(lines_of, st.data())
def test_lines_come_back_exactly_and_their_bytes_do_not_depend_on_order(
    lines: list[ArchivedLine], data: st.DataObject
) -> None:
    shuffled = data.draw(st.permutations(lines))

    assert decode_lines(encode_lines(lines)) == sorted(lines, key=lambda kept: kept.seq)
    assert lines_digest(encode_lines(shuffled)) == lines_digest(encode_lines(lines))


def test_pages_follow_the_spoken_order_and_show_one_more_for_the_next() -> None:
    # Строка записи получила seq выше живых, но сказана раньше.
    lines = [line(1, 0), line(2, 5000), line(3, 9000), line(7, 2000), line(8, 2000)]
    spoken = [(kept.start_ms, kept.seq) for kept in spoken_order(lines)]

    first = page_after(lines, None, 2)
    second = page_after(lines, (first[1].start_ms, first[1].seq), 2)
    last = page_after(lines, (second[1].start_ms, second[1].seq), 2)

    assert spoken == [(0, 1), (2000, 7), (2000, 8), (5000, 2), (9000, 3)]
    assert [kept.seq for kept in first] == [1, 7, 8]
    assert [kept.seq for kept in second] == [8, 2, 3]
    assert [kept.seq for kept in last] == [3]
