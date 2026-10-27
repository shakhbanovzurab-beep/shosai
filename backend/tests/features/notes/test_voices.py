"""Voices carried across the cuts of a long recording (ADR 0073): matched, kept apart, once."""

from itertools import pairwise

from hypothesis import given
from hypothesis import strategies as st

from shosai.features.notes.domain.recordings import Part
from shosai.features.notes.domain.voices import HeardPart, Segment, joined

CUT = 5_400_000


def heard(own: Part, *said: tuple[int, int, int | None]) -> HeardPart:
    """A part with segments `(start, end, voice)` over what it heard."""
    return HeardPart(own.start_ms, own.end_ms, tuple(Segment(s, e, f"{s}", v) for s, e, v in said))


def voices(segments: list[Segment]) -> list[tuple[int, int | None]]:
    return [(s.start_ms, s.speaker) for s in segments]


def test_one_part_keeps_its_voices_and_its_order() -> None:
    part = heard(Part(0, 60_000), (5_000, 9_000, 3), (0, 4_000, 7), (10_000, 12_000, None))

    assert voices(joined([part])) == [(0, 1), (5_000, 0), (10_000, None)]


def test_a_voice_speaking_over_the_cut_keeps_its_number_and_the_minutes_are_written_once() -> None:
    first = heard(
        Part(0, CUT), (10_000, 20_000, 0), (30_000, 40_000, 1),
        (CUT - 40_000, CUT - 30_000, 0), (CUT + 10_000, CUT + 20_000, 1),
    )  # fmt: skip
    second = heard(
        Part(CUT, 9_000_000), (CUT - 40_000, CUT - 30_000, 4), (CUT + 10_000, CUT + 20_000, 2),
        (CUT + 100_000, CUT + 110_000, 4),
    )  # fmt: skip

    assert voices(joined([first, second])) == [
        (10_000, 0), (30_000, 1), (CUT - 40_000, 0), (CUT + 10_000, 1), (CUT + 100_000, 0),
    ]  # fmt: skip


def test_a_voice_silent_over_the_cut_or_matched_too_little_gets_a_new_number() -> None:
    first = heard(Part(0, CUT), (10_000, 20_000, 0), (CUT - 20_000, CUT - 18_000, 1))
    second = heard(
        Part(CUT, 9_000_000), (CUT - 20_000, CUT - 18_000, 3), (CUT + 30_000, CUT + 35_000, 3),
        (CUT + 200_000, CUT + 210_000, 5),
    )  # fmt: skip

    assert voices(joined([first, second])) == [
        (10_000, 0), (CUT - 20_000, 1), (CUT + 30_000, 2), (CUT + 200_000, 3),
    ]  # fmt: skip


def test_a_voice_split_between_two_earlier_ones_is_not_merged() -> None:
    first = heard(Part(0, CUT), (CUT - 50_000, CUT - 40_000, 0), (CUT - 40_000, CUT - 30_000, 1))
    second = heard(
        Part(CUT, 9_000_000), (CUT - 50_000, CUT - 30_000, 6), (CUT + 5_000, CUT + 9_000, 6)
    )

    assert voices(joined([first, second])) == [
        (CUT - 50_000, 0),
        (CUT - 40_000, 1),
        (CUT + 5_000, 2),
    ]


def test_the_owner_keeps_one_number_in_every_part_by_the_me_lines() -> None:
    me = [(1_000, 9_000), (CUT + 300_000, CUT + 309_000)]
    first = heard(Part(0, CUT), (0, 10_000, 2), (20_000, 30_000, 0))
    second = heard(Part(CUT, 9_000_000), (CUT + 300_000, CUT + 310_000, 1))

    assert voices(joined([first, second], me)) == [(0, 1), (20_000, 0), (CUT + 300_000, 1)]


@given(
    st.lists(
        st.tuples(st.integers(0, 3 * CUT), st.integers(500, 30_000), st.integers(0, 3)),
        max_size=60,
    ),
    st.integers(1, 3),
)
def test_every_segment_heard_twice_is_written_once(
    said: list[tuple[int, int, int]], cuts: int
) -> None:
    timeline = sorted({(start, start + length, voice) for start, length, voice in said})
    end = 3 * CUT + 30_000
    bounds = [round(end * n / (cuts + 1)) for n in range(cuts + 2)]
    parts = []
    for low, high in pairwise(bounds):
        span = Part(low, high).heard(end)
        inside = [s for s in timeline if s[0] < span.end_ms and s[1] > span.start_ms]
        parts.append(heard(Part(low, high), *inside))

    written = joined(parts)

    assert [(s.start_ms, s.end_ms) for s in written] == [(s, e) for s, e, _ in timeline]
