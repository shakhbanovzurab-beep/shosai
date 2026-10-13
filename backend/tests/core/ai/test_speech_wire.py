"""The speech answers parsed without a network: usage, segments and speaker turns."""

from decimal import Decimal

import pytest

from shosai.core.ai.adapters.audio_formats import audio_format
from shosai.core.ai.adapters.openrouter_audio import segments_of, transcription_usage
from shosai.core.ai.adapters.pyannote import turns_of
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


@pytest.mark.parametrize(
    "job",
    [
        {},
        {"output": {"diarization": "none"}},
        {"output": {"diarization": [{"speaker": "", "start": 0, "end": 1}]}},
        {"output": {"diarization": [{"speaker": "A", "start": 2, "end": 1}]}},
    ],
)
def test_a_malformed_job_output_is_a_provider_error(job: dict[str, object]) -> None:
    with pytest.raises(AiCallError) as failed:
        turns_of(job)

    assert failed.value.failure is AiFailure.PROVIDER_ERROR


def test_turns_are_ordered_by_time_before_speakers_are_numbered() -> None:
    job = {"output": {"diarization": [
        {"speaker": "B", "start": 5.0, "end": 6.0},
        {"speaker": "A", "start": 1.0, "end": 2.0},
    ]}}  # fmt: skip

    assert [(t.start_ms, t.speaker) for t in turns_of(job)] == [(1000, 0), (5000, 1)]


@pytest.mark.parametrize(
    ("media_type", "expected"),
    [("audio/webm;codecs=opus", "webm"), ("AUDIO/MPEG", "mp3"), ("audio/x-unknown", None)],
)
def test_a_recording_format_is_named_by_its_base_type(
    media_type: str, expected: str | None
) -> None:
    assert audio_format(media_type) == expected
