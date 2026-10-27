"""Speakers laid over a recording's text: the voices marked, their numbers, the owner."""

from hypothesis import given
from hypothesis import strategies as st

from shosai.features.notes.domain.alignment import VoiceIndex, aligned, covered, talk_times
from shosai.features.notes.domain.lines import Line
from shosai.features.notes.domain.voices import HeardPart, Segment, shared_ms


def whole(*segments: Segment, end_ms: int = 600_000) -> list[HeardPart]:
    """A recording heard in one part."""
    return [HeardPart(0, end_ms, segments)]


def test_voices_are_numbered_as_they_first_speak_and_an_unmarked_segment_has_none() -> None:
    result = aligned(
        whole(
            Segment(60_000, 62_000, "Hi.", 4), Segment(63_000, 65_000, "Hey.", 1),
            Segment(66_000, 68_000, "So.", 4), Segment(69_000, 70_000, "Hm.", None),
        ),
        lead_ms=60_000,
    )  # fmt: skip

    assert [(p.start_ms, p.speaker) for p in result.pieces] == [
        (0, 0), (3_000, 1), (6_000, 0), (9_000, None),
    ]  # fmt: skip
    assert (result.speakers, result.owner) == (2, None)


def test_a_recording_started_early_is_moved_back_and_held_at_the_meeting_s_start() -> None:
    early = aligned(
        whole(Segment(1_000, 4_000, "Warm-up."), Segment(5_000, 7_000, "Go.")), lead_ms=2_000
    )
    late = aligned(whole(Segment(0, 1_000, "Late.")), lead_ms=-5_000)

    assert [(p.start_ms, p.end_ms) for p in early.pieces] == [(0, 2_000), (3_000, 5_000)]
    assert [(p.start_ms, p.end_ms) for p in late.pieces] == [(5_000, 6_000)]
    assert (covered(2_000, 60_000), covered(-5_000, 60_000)) == ((0, 58_000), (5_000, 65_000))


def test_the_owner_is_the_voice_most_over_the_live_me_lines() -> None:
    parts = whole(Segment(0, 4_500, "Mine.", 6), Segment(4_500, 9_000, "Theirs.", 3))

    owner_second = aligned(parts, lead_ms=2_000, me=[(3_000, 7_000)])
    owner_first = aligned(parts, lead_ms=2_000, me=[(0, 1_500)])
    nobody = aligned(parts, lead_ms=2_000, me=[(30_000, 40_000)])

    assert (owner_second.owner, owner_first.owner, nobody.owner) == (1, 0, None)


def test_talk_time_sums_each_voice_s_lines() -> None:
    lines = [Line(0, 4_000, "a", 0), Line(4_000, 9_000, "b", 1), Line(9_000, 10_000, "c", 0)]

    assert talk_times([*lines, Line(10_000, 12_000, "d", None)], 2) == [5_000, 5_000]


spans = st.tuples(st.integers(0, 600_000), st.integers(1, 40_000)).map(
    lambda s: (s[0], s[0] + s[1])
)


@given(
    st.lists(st.tuples(spans, st.integers(0, 5) | st.none()), max_size=40),
    st.lists(spans, min_size=1, max_size=10),
)
def test_the_buckets_find_what_a_full_scan_finds(
    voiced: list[tuple[tuple[int, int], int | None]], asked: list[tuple[int, int]]
) -> None:
    segments = [Segment(start, end, "x", voice) for (start, end), voice in voiced]
    index = VoiceIndex(segments)

    for span in asked:
        expected: dict[int, int] = {}
        for segment in segments:
            shared = shared_ms(span, (segment.start_ms, segment.end_ms))
            if segment.speaker is not None and shared:
                expected[segment.speaker] = expected.get(segment.speaker, 0) + shared
        assert index.shares(span) == expected
