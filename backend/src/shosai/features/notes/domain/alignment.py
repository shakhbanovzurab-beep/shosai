"""Speakers laid over a recording's transcript (plan §3.4 flow 5, MT-D3, ADR 0073).

The transcription marks a voice on each segment, part by part; the parts' voices are joined
across their cuts (`domain/voices.py`) and numbered again by their first appearance in the
text, so a voice that carries no segment gets no number. A desktop recording starts
`lead_ms` before the meeting did (the clients measure it): its time minus the lead is the
meeting's, and speech recorded before the meeting's start is held at its start. Its owner
is the voice whose segments overlap most with the live "me" lines of the span it covers.
Segments are looked up by 10-second buckets, so a six-hour recording aligns in linear time.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from shosai.features.notes.domain.lines import Line, Piece
from shosai.features.notes.domain.voices import HeardPart, Segment, joined, shared_ms

BUCKET_MS: Final = 10_000


@dataclass(frozen=True, slots=True)
class Aligned:
    """The pieces with their speakers, numbered by first appearance, and the owner's number."""

    pieces: tuple[Piece, ...]
    speakers: int
    owner: int | None


def covered(lead_ms: int, duration_ms: int) -> tuple[int, int]:
    """The span of the meeting a recording covers, `lead_ms` early, `duration_ms` long."""
    return max(0, -lead_ms), max(0, duration_ms - lead_ms)


class VoiceIndex:
    """Segments with a voice by the 10-second buckets they touch."""

    def __init__(self, segments: Iterable[Segment]) -> None:
        self._voiced = tuple(s for s in segments if s.speaker is not None)
        self._buckets: dict[int, list[int]] = defaultdict(list)
        for number, segment in enumerate(self._voiced):
            for bucket in range(segment.start_ms // BUCKET_MS, segment.end_ms // BUCKET_MS + 1):
                self._buckets[bucket].append(number)

    def shares(self, span: tuple[int, int]) -> dict[int, int]:
        """Each speaker's milliseconds within the span."""
        seen: set[int] = set()
        shared: dict[int, int] = defaultdict(int)
        for bucket in range(span[0] // BUCKET_MS, span[1] // BUCKET_MS + 1):
            for number in self._buckets.get(bucket, ()):
                if number not in seen:
                    seen.add(number)
                    segment = self._voiced[number]
                    if segment.speaker is not None:
                        shared[segment.speaker] += shared_ms(
                            span, (segment.start_ms, segment.end_ms)
                        )
        return {speaker: ms for speaker, ms in shared.items() if ms > 0}


def aligned(
    parts: Sequence[HeardPart],
    *,
    lead_ms: int = 0,
    me: Sequence[tuple[int, int]] = (),
) -> Aligned:
    """The parts' segments as pieces of the meeting, the recording `lead_ms` early, with speakers.

    `me` are the spans of the live "me" lines the recording covers, in the meeting's time.
    """
    heard = [(start + lead_ms, end + lead_ms) for start, end in me]
    segments = joined(parts, heard)
    numbers: dict[int, int] = {}
    for segment in segments:
        if segment.speaker is not None and segment.speaker not in numbers:
            numbers[segment.speaker] = len(numbers)
    pieces = tuple(
        Piece(
            max(0, segment.start_ms - lead_ms), max(0, segment.end_ms - lead_ms), segment.text,
            None if segment.speaker is None else numbers[segment.speaker],
        )
        for segment in segments
    )  # fmt: skip
    return Aligned(pieces, len(numbers), _owner(VoiceIndex(segments), heard, numbers))


def _owner(
    index: VoiceIndex, heard: Sequence[tuple[int, int]], numbers: Mapping[int, int]
) -> int | None:
    totals: dict[int, int] = defaultdict(int)
    for span in heard:
        for speaker, ms in index.shares(span).items():
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
