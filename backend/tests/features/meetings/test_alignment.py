"""Speakers laid over a recording's text: who said each segment, their numbers, the owner."""

from hypothesis import given
from hypothesis import strategies as st

from shosai.features.meetings.domain.alignment import (
    Segment,
    Turn,
    TurnIndex,
    aligned,
    covered,
    overlap,
    speaker_of,
    talk_times,
)
from shosai.features.meetings.domain.lines import Line


def test_a_segment_takes_the_voice_covering_most_of_it_and_none_without_one() -> None:
    index = TurnIndex([Turn(0, 4_000, 5), Turn(3_000, 12_000, 2), Turn(20_000, 21_000, 7)])

    assert speaker_of(index, Segment(1_000, 5_000, "a")) == 5
    assert speaker_of(index, Segment(3_500, 11_000, "b")) == 2
    assert speaker_of(index, Segment(3_000, 5_000, "tie")) == 2
    assert speaker_of(index, Segment(14_000, 18_000, "none")) is None


def test_voices_are_numbered_as_they_first_speak_and_a_silent_one_gets_none() -> None:
    segments = [
        Segment(60_000, 62_000, "Hi."),
        Segment(63_000, 65_000, "Hey."),
        Segment(66_000, 68_000, "So."),
    ]
    turns = [
        Turn(60_000, 62_500, 4),
        Turn(62_500, 65_500, 1),
        Turn(65_500, 69_000, 4),
        Turn(69_000, 70_000, 9),
    ]

    result = aligned(segments, turns, lead_ms=60_000)

    assert [(p.start_ms, p.speaker) for p in result.pieces] == [(0, 0), (3_000, 1), (6_000, 0)]
    assert (result.speakers, result.owner) == (2, None)


def test_a_recording_started_early_is_moved_back_and_held_at_the_meeting_s_start() -> None:
    early = aligned(
        [Segment(1_000, 4_000, "Warm-up."), Segment(5_000, 7_000, "Go.")], [], lead_ms=2_000
    )
    late = aligned([Segment(0, 1_000, "Late.")], [], lead_ms=-5_000)

    assert [(p.start_ms, p.end_ms) for p in early.pieces] == [(0, 2_000), (3_000, 5_000)]
    assert [(p.start_ms, p.end_ms) for p in late.pieces] == [(5_000, 6_000)]
    assert (covered(2_000, 60_000), covered(-5_000, 60_000)) == ((0, 58_000), (5_000, 65_000))


def test_the_owner_is_the_voice_most_over_the_live_me_lines() -> None:
    segments = [Segment(0, 4_000, "Mine."), Segment(5_000, 9_000, "Theirs.")]
    turns = [Turn(0, 4_500, 6), Turn(4_500, 9_000, 3)]

    owner_second = aligned(segments, turns, lead_ms=2_000, me=[(3_000, 7_000)])
    owner_first = aligned(segments, turns, lead_ms=2_000, me=[(0, 1_500)])
    nobody = aligned(segments, turns, lead_ms=2_000, me=[(30_000, 40_000)])

    assert (owner_second.owner, owner_first.owner, nobody.owner) == (1, 0, None)


def test_talk_time_sums_each_voice_s_lines() -> None:
    lines = [Line(0, 4_000, "a", 0), Line(4_000, 9_000, "b", 1), Line(9_000, 10_000, "c", 0)]

    assert talk_times([*lines, Line(10_000, 12_000, "d", None)], 2) == [5_000, 5_000]


spans = st.tuples(st.integers(0, 600_000), st.integers(1, 40_000)).map(
    lambda s: (s[0], s[0] + s[1])
)


@given(
    st.lists(spans, max_size=40),
    st.lists(st.tuples(spans, st.integers(0, 5)), max_size=40).map(lambda turns: turns * 2),
)
def test_the_buckets_find_what_a_full_scan_finds(
    segment_spans: list[tuple[int, int]], turn_spans: list[tuple[tuple[int, int], int]]
) -> None:
    turns = [Turn(start, end, speaker) for (start, end), speaker in turn_spans]
    segments = [Segment(start, end, "x") for start, end in sorted(segment_spans)]

    result = aligned(segments, turns)

    numbers: dict[int, int] = {}
    for segment, piece in zip(segments, result.pieces, strict=True):
        shares: dict[int, int] = {}
        for turn in turns:
            shared = overlap((segment.start_ms, segment.end_ms), (turn.start_ms, turn.end_ms))
            if shared:
                shares[turn.speaker] = shares.get(turn.speaker, 0) + shared
        expected = min(shares, key=lambda s: (-shares[s], s)) if shares else None
        if expected is not None:
            numbers.setdefault(expected, len(numbers))
        assert piece.speaker == (None if expected is None else numbers[expected])
    assert result.speakers == len(numbers)
