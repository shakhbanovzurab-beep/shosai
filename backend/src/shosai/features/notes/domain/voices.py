"""Voices carried across the cuts of a long recording (ADR 0073).

The transcription model marks the speakers of each part on its own, numbering them anew.
Two neighbouring parts both hear the two minutes around their cut: a voice of the later
part takes the number of the earlier part's voice it speaks with at the same time there,
when at least two thirds of its shared speech and at least 3 seconds agree; the pairs are
taken from the largest agreement down, one to one. In a desktop recording, the voice most
over the live "me" lines is the owner in every part. Any other voice gets a new number: a
wrong merge would give one person's words to another. Each part keeps the segments whose
middle lies within its own span, so the minutes heard twice are written once.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from shosai.features.notes.domain.recordings import SEAM_MS

AGREEMENT: Final = 2 / 3
AGREED_MS_MIN: Final = 3_000


@dataclass(frozen=True, slots=True)
class Segment:
    """A timed piece of the transcription from the recording's start, with its voice if marked."""

    start_ms: int
    end_ms: int
    text: str
    speaker: int | None = None

    @property
    def middle_ms(self) -> int:
        """The segment's middle."""
        return (self.start_ms + self.end_ms) // 2


@dataclass(frozen=True, slots=True)
class HeardPart:
    """A part's own span and the segments of all it was heard over, voices as it numbered them."""

    start_ms: int
    end_ms: int
    segments: tuple[Segment, ...]


def shared_ms(a: tuple[int, int], b: tuple[int, int]) -> int:
    """How many milliseconds two spans share."""
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def voice_over(segments: Iterable[Segment], spans: Sequence[tuple[int, int]]) -> int | None:
    """The voice speaking most over the spans, when at least 3 seconds of it; ties to the lowest."""
    totals: dict[int, int] = defaultdict(int)
    for segment in segments:
        if segment.speaker is None:
            continue
        for span in spans:
            totals[segment.speaker] += shared_ms((segment.start_ms, segment.end_ms), span)
    held = {voice: ms for voice, ms in totals.items() if ms >= AGREED_MS_MIN}
    return min(held, key=lambda voice: (-held[voice], voice)) if held else None


def agreement(
    earlier: Sequence[Segment], later: Sequence[Segment], window: tuple[int, int]
) -> dict[tuple[int, int], int]:
    """Milliseconds each later voice and each earlier voice speak at once within the window."""
    shared: dict[tuple[int, int], int] = defaultdict(int)
    before = [
        (s.speaker, _span(s))
        for s in earlier
        if s.speaker is not None and shared_ms(_span(s), window)
    ]
    for segment in later:
        if segment.speaker is None or not shared_ms(_span(segment), window):
            continue
        for voice, span in before:
            both = shared_ms(_span(segment), span)
            if both:
                shared[(segment.speaker, voice)] += both
    return shared


def matched(shared: dict[tuple[int, int], int], taken: dict[int, int]) -> dict[int, int]:
    """Later voices to earlier ones, from the largest agreement down, one to one.

    `taken` are pairs already fixed (the owner); they stay and their voices are not offered.
    """
    pairs = dict(taken)
    used = set(taken.values())
    totals: dict[int, int] = defaultdict(int)
    for (later, _), ms in shared.items():
        totals[later] += ms
    for (later, earlier), ms in sorted(shared.items(), key=lambda item: (-item[1], item[0])):
        if later in pairs or earlier in used:
            continue
        if ms >= AGREED_MS_MIN and ms >= AGREEMENT * totals[later]:
            pairs[later] = earlier
            used.add(earlier)
    return pairs


def joined(parts: Sequence[HeardPart], me: Sequence[tuple[int, int]] = ()) -> list[Segment]:
    """The parts' segments in time order with one numbering of voices across the cuts.

    `me` are the spans of the live "me" lines in the recording's time.
    """
    result: list[Segment] = []
    earlier: list[Segment] = []
    owner: int | None = None
    count = 0
    for index, part in enumerate(parts):
        own = _owned(parts, index)
        mine = voice_over(filter(own, part.segments), me) if me else None
        taken = {mine: owner} if mine is not None and owner is not None else {}
        window = (part.start_ms - SEAM_MS, part.start_ms + SEAM_MS)
        pairs = matched(agreement(earlier, part.segments, window), taken)
        for voice in sorted({s.speaker for s in part.segments if s.speaker is not None}):
            if voice not in pairs:
                pairs[voice] = count
                count += 1
        if mine is not None and owner is None:
            owner = pairs[mine]
        earlier = [_renumbered(segment, pairs) for segment in part.segments]
        result.extend(filter(own, earlier))
    return sorted(result, key=lambda s: (s.start_ms, s.end_ms))


def _owned(parts: Sequence[HeardPart], index: int) -> Callable[[Segment], bool]:
    """Whether a segment is the part's: its middle within the part's span; the first part
    takes everything before it and the last everything after it."""
    part = parts[index]
    low = part.start_ms if index > 0 else None
    high = part.end_ms if index < len(parts) - 1 else None
    return lambda s: (low is None or s.middle_ms >= low) and (high is None or s.middle_ms < high)


def _span(segment: Segment) -> tuple[int, int]:
    return segment.start_ms, segment.end_ms


def _renumbered(segment: Segment, pairs: dict[int, int]) -> Segment:
    if segment.speaker is None:
        return segment
    return Segment(segment.start_ms, segment.end_ms, segment.text, pairs[segment.speaker])
