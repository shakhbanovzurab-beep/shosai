"""Transcript lines: identity, offsets and shaping recognised speech (meetings plan step 1)."""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.features.meetings.domain.lines import (
    LINE_MAX_MS,
    MERGE_GAP_MS,
    TARGET_MS,
    Line,
    Piece,
    shape_lines,
)
from shosai.features.meetings.domain.transcript import (
    LINE_TEXT_MAX,
    fitted_text,
    fresh_seqs,
    offset_ms,
)

START = datetime(2026, 10, 19, 9, tzinfo=UTC)
words = st.sampled_from(
    ["Да.", "договорились", "срок", "пятница?", "OK!", "会議。", "نعم؟", "ठीक।"]
)


@st.composite
def pieces(draw: st.DrawFn) -> list[Piece]:
    result: list[Piece] = []
    at = 0
    for _ in range(draw(st.integers(min_value=0, max_value=12))):
        # Куски не перекрываются: так строка однозначно знает, чьи куски в ней начались.
        at += draw(st.integers(min_value=1, max_value=2_000))
        length = draw(st.integers(min_value=1, max_value=90_000))
        text = " ".join(draw(st.lists(words, min_size=1, max_size=40)))
        result.append(Piece(at, at + length, text, draw(st.none() | st.integers(0, 3))))
        at += length
    return result


def squeezed(texts: list[str]) -> str:
    return "".join("".join(texts).split())


@given(recognised=pieces())
def test_no_text_is_lost_and_every_line_keeps_its_caps(recognised: list[Piece]) -> None:
    lines = shape_lines(recognised)

    assert squeezed([line.text for line in lines]) == squeezed([p.text for p in recognised])
    assert all(line.end_ms - line.start_ms <= LINE_MAX_MS for line in lines)
    assert all(0 < len(line.text) <= LINE_TEXT_MAX for line in lines)
    assert [line.start_ms for line in lines] == sorted(line.start_ms for line in lines)


@given(recognised=pieces())
def test_a_line_is_one_speakers_speech_without_a_long_gap(recognised: list[Piece]) -> None:
    for line in shape_lines(recognised):
        inside = [p for p in recognised if line.start_ms <= p.start_ms < line.end_ms]
        assert {p.speaker for p in inside if p.text.strip()} <= {line.speaker}


def test_a_minute_long_piece_becomes_lines_of_about_ten_seconds_at_sentence_ends() -> None:
    sentence = "Мы обсудили сроки и бюджет проекта. "
    piece = Piece(0, 60_000, sentence * 12, speaker=1)

    lines = shape_lines([piece])

    assert len(lines) >= 5
    assert all(line.text.endswith(".") for line in lines)
    assert all(line.end_ms - line.start_ms >= TARGET_MS for line in lines[:-1])


def test_a_long_sentence_without_marks_is_cut_between_words_and_a_wide_script_between_signs() -> (
    None
):
    latin = shape_lines([Piece(0, 120_000, " ".join(["слово"] * 400), speaker=0)])
    wide = shape_lines([Piece(0, 120_000, "会議" * 1500, speaker=0)])

    assert all(not line.text.startswith("лово") for line in latin)
    assert all(line.end_ms - line.start_ms <= LINE_MAX_MS for line in latin + wide)
    assert squeezed([line.text for line in wide]) == "会議" * 1500


def test_another_speaker_or_a_gap_starts_a_new_line() -> None:
    lines = shape_lines([
        Piece(0, 1_000, "Привет.", speaker=0),
        Piece(1_100, 2_000, "Привет.", speaker=1),
        Piece(2_000 + MERGE_GAP_MS + 1, 4_000, "Начнём.", speaker=1),
    ])  # fmt: skip

    assert [(line.speaker, line.text) for line in lines] == [
        (0, "Привет."),
        (1, "Привет."),
        (1, "Начнём."),
    ]


def test_wide_script_parts_join_without_a_space() -> None:
    lines = shape_lines(
        [Piece(0, 1_000, "会議", speaker=0), Piece(1_000, 2_000, "です。", speaker=0)]
    )

    assert lines == [Line(0, 2_000, "会議です。", 0)]


def test_offsets_seqs_and_text_caps() -> None:
    assert offset_ms(START, START + timedelta(seconds=1.5)) == 1_500
    assert offset_ms(START, START - timedelta(seconds=1)) == 0
    assert list(fresh_seqs(41, 3)) == [42, 43, 44]
    assert fitted_text("  Да.  ") == ("Да.", False)
    text, cut = fitted_text("я" * (LINE_TEXT_MAX + 5))
    assert (len(text), cut) == (LINE_TEXT_MAX, True)
    with pytest.raises(ValueError, match="неотрицательные"):
        fresh_seqs(-1, 1)


def test_a_piece_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValueError, match="конец"):
        Piece(5, 4, "Да.")
