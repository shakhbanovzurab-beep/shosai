"""Speakers laid over a recording's transcript (plan §3.4 flow 5, MT-D3, ADR 0043).

The transcription's timed segments and pyannote's speaker turns are two answers about the
same audio. A segment takes the speaker whose turns cover most of it, or none when no turn
touches it; the speakers are then numbered again by their first appearance in the text, so
a voice that carries no segment gets no number. For a desktop recording the owner is the
speaker whose turns overlap most with the live "me" lines of the span the recording covers.
Turns are looked up by 10-second buckets, so a six-hour recording aligns in linear time.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from shosai.features.meetings.domain.lines import Line, Piece

BUCKET_MS: Final = 10_000


@dataclass(frozen=True, slots=True)
class Segment:
    """A timed piece of the transcription, from the recording's start."""

    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True, slots=True)
class Turn:
    """When one of pyannote's speakers spoke, from the recording's start."""

    start_ms: int
    end_ms: int
    speaker: int


@dataclass(frozen=True, slots=True)
class Aligned:
    """The pieces with their speakers, numbered by first appearance, and the owner's number."""

    pieces: tuple[Piece, ...]
    speakers: int
    owner: int | None


def overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    """How many milliseconds two spans share."""
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


class TurnIndex:
    """Turns by the 10-second buckets they touch."""

    def __init__(self, turns: Iterable[Turn]) -> None:
        self._turns = tuple(turns)
        self._buckets: dict[int, list[int]] = defaultdict(list)
        for number, turn in enumerate(self._turns):
            for bucket in range(turn.start_ms // BUCKET_MS, turn.end_ms // BUCKET_MS + 1):
                self._buckets[bucket].append(number)

    def shares(self, span: tuple[int, int]) -> dict[int, int]:
        """Each speaker's milliseconds within the span."""
        seen: set[int] = set()
        shared: dict[int, int] = defaultdict(int)
        for bucket in range(span[0] // BUCKET_MS, span[1] // BUCKET_MS + 1):
            for number in self._buckets.get(bucket, ()):
                if number not in seen:
                    seen.add(number)
                    turn = self._turns[number]
                    shared[turn.speaker] += overlap(span, (turn.start_ms, turn.end_ms))
        return {speaker: ms for speaker, ms in shared.items() if ms > 0}


def speaker_of(index: TurnIndex, segment: Segment) -> int | None:
    """The speaker covering most of the segment; the lowest number on a tie."""
    shares = index.shares((segment.start_ms, segment.end_ms))
    if not shares:
        return None
    return min(shares, key=lambda speaker: (-shares[speaker], speaker))


def aligned(
    segments: Sequence[Segment],
    turns: Sequence[Turn],
    *,
    lead_ms: int = 0,
    me: Sequence[tuple[int, int]] = (),
) -> Aligned:
    """The segments as pieces of the meeting, `lead_ms` after its start, with speakers.

    `me` are the spans of the live "me" lines the recording covers, in the meeting's time.
    """
    index = TurnIndex(turns)
    heard = [speaker_of(index, segment) for segment in segments]
    numbers: dict[int, int] = {}
    for speaker in heard:
        if speaker is not None and speaker not in numbers:
            numbers[speaker] = len(numbers)
    pieces = tuple(
        Piece(
            lead_ms + segment.start_ms, lead_ms + segment.end_ms, segment.text,
            None if speaker is None else numbers[speaker],
        )
        for segment, speaker in zip(segments, heard, strict=True)
    )  # fmt: skip
    return Aligned(pieces, len(numbers), _owner(index, me, lead_ms, numbers))


def _owner(
    index: TurnIndex, me: Sequence[tuple[int, int]], lead_ms: int, numbers: Mapping[int, int]
) -> int | None:
    totals: dict[int, int] = defaultdict(int)
    for start, end in me:
        for speaker, ms in index.shares((start - lead_ms, end - lead_ms)).items():
            totals[speaker] += ms
    carried = {speaker: ms for speaker, ms in totals.items() if speaker in numbers}
    if not carried:
        return None
    return numbers[min(carried, key=lambda speaker: (-carried[speaker], speaker))]


def talk_times(lines: Iterable[Line], speakers: int) -> list[int]:
    """Each numbered speaker's milliseconds of lines."""
    times = [0] * speakers
    for line in lines:
        if line.speaker is not None:
            times[line.speaker] += line.end_ms - line.start_ms
    return times
