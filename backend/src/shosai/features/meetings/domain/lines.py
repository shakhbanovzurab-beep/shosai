"""Recognised speech shaped into transcript lines (plan §1.2; draft 9f11c56bd, 3af4f01c9).

A transcription answers timed pieces of text, sometimes a minute long. A line is one
speaker's speech of about 10 seconds: a piece is split at sentence ends, a sentence too
long for one line is split between words (or between characters in scripts written
without spaces), and the parts are gathered into lines that break once they reach 10
seconds — at a sentence end or a pause of at least 250 ms — and always before 60 seconds,
2 000 characters, another speaker or a gap over 800 ms. Times inside a piece are spread by
the share of its characters. No text is ever dropped. Sentence ends are the terminal marks
of the platform's 16 languages; the pause is the fallback for speech without them.
"""

import math
import unicodedata
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, replace
from typing import Final

from shosai.features.meetings.domain.transcript import LINE_TEXT_MAX

TARGET_MS: Final = 10_000
LINE_MAX_MS: Final = 60_000
PAUSE_MS: Final = 250
MERGE_GAP_MS: Final = 800
# Знаки конца предложения в 16 языках платформы: латиница и кириллица, CJK, арабский
# вопросительный, деванагари.
TERMINATORS: Final = frozenset(".!?…。！？؟।॥")
# После этих знаков предложение кончается и без пробела.
WIDE_TERMINATORS: Final = frozenset("。！？")


@dataclass(frozen=True, slots=True)
class Piece:
    """A timed piece of recognised text and its speaker, if known."""

    start_ms: int
    end_ms: int
    text: str
    speaker: int | None = None

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms < self.start_ms:
            message = "кусок речи: начало от нуля, конец не раньше начала"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class Line:
    """One transcript line: its span, its text and its speaker."""

    start_ms: int
    end_ms: int
    text: str
    speaker: int | None


@dataclass(frozen=True, slots=True)
class _Unit:
    """A sentence or a part of one, with whether it ends a sentence."""

    piece: Piece
    ends_sentence: bool


def shape_lines(pieces: Iterable[Piece]) -> list[Line]:
    """The lines of a transcript from its recognised pieces, in time order."""
    ordered = sorted(
        (piece for piece in pieces if piece.text.strip()), key=lambda p: (p.start_ms, p.end_ms)
    )
    units = [unit for piece in ordered for unit in _short_units(piece)]
    lines: list[Line] = []
    current: list[_Unit] = []
    for unit in units:
        if current and _breaks(current, unit):
            lines.append(_line(current))
            current = []
        current.append(unit)
    if current:
        lines.append(_line(current))
    return lines


def _breaks(current: Sequence[_Unit], unit: _Unit) -> bool:
    first, last = current[0].piece, current[-1].piece
    gap = unit.piece.start_ms - last.end_ms
    if unit.piece.speaker != first.speaker or gap > MERGE_GAP_MS:
        return True
    if unit.piece.end_ms - first.start_ms > LINE_MAX_MS:
        return True
    if len(_joined([*current, unit])) > LINE_TEXT_MAX:
        return True
    reached = last.end_ms - first.start_ms >= TARGET_MS
    return reached and (current[-1].ends_sentence or gap >= PAUSE_MS)


def _line(units: Sequence[_Unit]) -> Line:
    return Line(
        start_ms=units[0].piece.start_ms,
        end_ms=max(unit.piece.end_ms for unit in units),
        text=_joined(units),
        speaker=units[0].piece.speaker,
    )


def _joined(units: Sequence[_Unit]) -> str:
    text = ""
    for unit in units:
        part = unit.piece.text
        if not part:
            continue
        if text and not text[-1].isspace() and not part[0].isspace() and _spaced(text[-1], part[0]):
            text += " "
        text += part
    return text.strip()


def _spaced(left: str, right: str) -> bool:
    """Whether two parts meeting at these characters are separated by a space."""
    return not (_wide(left) or _wide(right))


def _wide(char: str) -> bool:
    return unicodedata.east_asian_width(char) in {"W", "F"}


def _short_units(piece: Piece) -> Iterator[_Unit]:
    for sentence in _sentences(piece):
        yield from (unit for unit in _within_caps(sentence) if unit.piece.text.strip())


def _sentences(piece: Piece) -> Iterator[_Unit]:
    text = piece.text
    begin = 0
    for index, char in enumerate(text):
        nxt = text[index + 1] if index + 1 < len(text) else ""
        ends = char in TERMINATORS and (not nxt or nxt.isspace() or char in WIDE_TERMINATORS)
        if ends and nxt not in TERMINATORS:
            yield _Unit(_slice(piece, begin, index + 1), ends_sentence=True)
            begin = index + 1
    if text[begin:].strip():
        yield _Unit(_slice(piece, begin, len(text)), ends_sentence=False)


def _within_caps(unit: _Unit) -> Iterator[_Unit]:
    piece = unit.piece
    length = len(piece.text)
    duration = piece.end_ms - piece.start_ms
    if duration <= LINE_MAX_MS and length <= LINE_TEXT_MAX:
        yield unit
        return
    chunks = max(math.ceil(duration / TARGET_MS), math.ceil(length / LINE_TEXT_MAX))
    cuts = _cuts(piece.text, chunks)
    for number, (begin, end) in enumerate(zip([0, *cuts], [*cuts, length], strict=True)):
        part = _slice(piece, begin, end)
        # Кусок, где почти нет текста на долгую речь, делить нечем: его конец прижимается.
        part = replace(part, end_ms=min(part.end_ms, part.start_ms + LINE_MAX_MS))
        last = number == len(cuts)
        yield _Unit(part, ends_sentence=last and unit.ends_sentence)


def _cuts(text: str, chunks: int) -> list[int]:
    """Where to cut `text` into about `chunks` parts: after a space, else between characters.

    A part is never longer than a line may be: a word longer than that is cut inside.
    """
    step = len(text) / chunks
    cuts: list[int] = []
    for number in range(1, chunks):
        previous = cuts[-1] if cuts else 0
        aim = round(number * step)
        space = text.rfind(" ", previous, aim)
        cut = space + 1 if space > previous else aim
        if previous < cut < len(text):
            cuts.append(cut)
    bounded: list[int] = []
    for begin, end in zip([0, *cuts], [*cuts, len(text)], strict=True):
        bounded.extend(range(begin + LINE_TEXT_MAX, end, LINE_TEXT_MAX))
        if end < len(text):
            bounded.append(end)
    return bounded


def _slice(piece: Piece, begin: int, end: int) -> Piece:
    length = max(len(piece.text), 1)
    duration = piece.end_ms - piece.start_ms
    return replace(
        piece,
        start_ms=piece.start_ms + duration * begin // length,
        end_ms=piece.start_ms + duration * end // length,
        text=piece.text[begin:end],
    )
