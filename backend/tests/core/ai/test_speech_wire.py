"""The speech answers parsed without a network: usage, segments and speakers from words."""

from decimal import Decimal

import pytest

from shosai.core.ai.adapters.audio_formats import audio_format
from shosai.core.ai.adapters.openrouter_audio import (
    segments_of,
    speaker_segments,
    transcription_usage,
)
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.results import Unit, Usage


def test_a_token_billed_transcription_without_seconds_has_no_audio_unit() -> None:
    usage = transcription_usage({"input_tokens": 10, "output_tokens": 2, "cost": "0.0001"})

    assert usage == Usage(input_tokens=10, output_tokens=2, reported_cost_usd=Decimal("0.0001"))


def test_seconds_of_audio_are_the_unit_of_a_duration_billed_one() -> None:
    usage = transcription_usage({"seconds": 12.5})

    assert (usage.units, usage.unit, usage.reported_cost_usd) == (
        Decimal("12.5"), Unit.AUDIO_SECOND, None,
    )  # fmt: skip


@pytest.mark.parametrize(
    "segments",
    ["not a list", [{"start": 2.0, "end": 1.0}], [{"start": "0", "end": 1.0}], [None]],
)
def test_a_malformed_segment_is_a_provider_error(segments: object) -> None:
    with pytest.raises(AiCallError) as failed:
        segments_of(segments)

    assert failed.value.failure is AiFailure.PROVIDER_ERROR


def word(text: str, start: float, end: float, speaker: int | None) -> dict[str, object]:
    """A word as Scribe answers it through OpenRouter."""
    return {"word": text, "start": start, "end": end, "speaker": speaker}


def test_a_voice_s_words_are_one_segment_until_another_voice_or_a_pause() -> None:
    words = [
        word("Да,", 0.0, 0.3, 0), word("согласен.", 0.35, 0.9, 0), word("Хорошо.", 1.0, 1.4, 1),
        word("Тогда", 1.5, 1.8, 1), word("завтра.", 3.0, 3.5, 1), word(" ", 3.5, 3.6, None),
    ]  # fmt: skip

    segments = speaker_segments("Да, согласен. Хорошо. Тогда завтра.", words)

    assert [(s.start_ms, s.end_ms, s.text, s.speaker) for s in segments] == [
        (0, 900, "Да, согласен.", 0), (1000, 1800, "Хорошо. Тогда", 1), (3000, 3500, "завтра.", 1),
    ]  # fmt: skip


def test_a_script_without_spaces_keeps_the_answer_s_own_spacing() -> None:
    words = [word("你", 0.0, 0.1, 0), word("好", 0.1, 0.2, 0), word("。", 0.2, 0.2, 0),
             word("再", 0.3, 0.4, 0), word("见", 0.4, 0.5, 0)]  # fmt: skip

    [segment] = speaker_segments("你好。 再见", words)

    assert segment.text == "你好。 再见"


def test_a_word_missing_from_the_text_is_joined_by_spaces() -> None:
    segments = speaker_segments("Hello", [word("Hello", 0, 0.5, 0), word("there", 0.6, 1, 1)])

    assert [s.text for s in segments] == ["Hello", "there"]


@pytest.mark.parametrize("words", [None, [], [word("Hi", 0, 1, None)]])
def test_words_without_speakers_give_no_speaker_segments(words: object) -> None:
    assert speaker_segments("Hi", words) == ()


@pytest.mark.parametrize(
    "words",
    [[{"word": "Hi", "start": 2, "end": 1, "speaker": 0}], [{"start": 0, "end": 1}], [None]],
)
def test_a_malformed_word_is_a_provider_error(words: list[object]) -> None:
    with pytest.raises(AiCallError) as failed:
        speaker_segments("Hi", words)

    assert failed.value.failure is AiFailure.PROVIDER_ERROR


@pytest.mark.parametrize(
    ("media_type", "expected"),
    [("audio/webm;codecs=opus", "webm"), ("AUDIO/MPEG", "mp3"), ("audio/x-unknown", None)],
)
def test_a_recording_format_is_named_by_its_base_type(
    media_type: str, expected: str | None
) -> None:
    assert audio_format(media_type) == expected
