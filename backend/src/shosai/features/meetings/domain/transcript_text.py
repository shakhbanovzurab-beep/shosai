"""The transcript as a model reads it, cut to its budget (plan §3.4 flow 6; draft 46ec0dc66).

Each line is numbered and timed — `L12 [03:41] S2: …` — so the model cites lines, not times,
and the evidence is the cited lines' span. A transcript longer than one call may carry is
cut into windows of whole lines with an overlap of eight lines; the write-up reads the end of
the transcript that fits its budget, cut from the head by whole lines, so the meeting's
closing lines — where decisions often land — are always kept. Budgets are in characters.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

OVERLAP_LINES: Final = 8


@dataclass(frozen=True, slots=True)
class SpokenLine:
    """A line as the model reads it: its number, offset, length, speaker and text."""

    number: int
    start_ms: int
    duration_ms: int
    speaker: int | None
    text: str

    @property
    def end_ms(self) -> int:
        """When the line ends, from the meeting's start."""
        return self.start_ms + self.duration_ms


def clock(ms: int) -> str:
    """`mm:ss`, or `h:mm:ss` past an hour."""
    seconds = ms // 1000
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def rendered(line: SpokenLine) -> str:
    """One line for the model."""
    speaker = "S?" if line.speaker is None else f"S{line.speaker + 1}"
    return f"L{line.number} [{clock(line.start_ms)}] {speaker}: {line.text}"


def numbered(lines: Sequence[tuple[int, int, int | None, str]]) -> list[SpokenLine]:
    """Stored lines `(start_ms, duration_ms, speaker, text)` numbered from 1 in their order."""
    return [
        SpokenLine(number, start, length, speaker, text)
        for number, (start, length, speaker, text) in enumerate(lines, 1)
    ]


def windows(lines: Sequence[SpokenLine], budget: int) -> list[list[SpokenLine]]:
    """Windows of whole lines within `budget` characters, each overlapping the last by 8 lines.

    A line longer than the budget is a window of its own. Every line is in some window.
    """
    if budget < 1:
        message = "бюджет окна — хотя бы один символ"
        raise ValueError(message)
    result: list[list[SpokenLine]] = []
    start = 0
    while start < len(lines):
        size, end = 0, start
        while end < len(lines) and (end == start or size + len(rendered(lines[end])) + 1 <= budget):
            size += len(rendered(lines[end])) + 1
            end += 1
        result.append(list(lines[start:end]))
        if end >= len(lines):
            break
        start = max(end - OVERLAP_LINES, start + 1)
    return result


def tail(lines: Sequence[SpokenLine], budget: int) -> list[SpokenLine]:
    """The longest run of whole closing lines within `budget` characters (at least the last)."""
    kept: list[SpokenLine] = []
    size = 0
    for line in reversed(lines):
        cost = len(rendered(line)) + 1
        if kept and size + cost > budget:
            break
        kept.append(line)
        size += cost
    return list(reversed(kept))


def span(lines: Sequence[SpokenLine], first: int, last: int) -> tuple[int, int] | None:
    """The offsets from the start of line `first` to the end of line `last`, if both exist."""
    by_number = {line.number: line for line in lines}
    if first > last or first not in by_number or last not in by_number:
        return None
    return by_number[first].start_ms, by_number[last].end_ms
