"""Live sessions' wire parsed without a network: setup, usage, failures and the billing floor."""

from collections.abc import Callable
from decimal import Decimal

import pytest
from google.genai import errors

from shosai.core.ai.adapters.gemini_live import failure_of, live_config
from shosai.core.ai.adapters.openai_realtime import event_of, realtime_usage, session_update
from shosai.core.ai.errors import AiFailure
from shosai.core.ai.requests import LiveTranscriptionSetup, NativeTranslationSetup, VoiceSetup
from shosai.core.ai.results import Unit, Usage
from shosai.core.ai.sessions.live import shortfall


@pytest.mark.parametrize(
    ("model", "languages", "expected"),
    [
        ("gpt-live-transcribe", ("ru", "en"), {"languages": ["ru", "en"]}),
        ("gpt-realtime-whisper", ("ru",), {"language": "ru"}),
        ("gpt-realtime-whisper", ("ru", "en"), {}),
        ("gpt-live-transcribe", (), {}),
    ],
)
def test_languages_go_in_the_field_the_model_takes(
    model: str, languages: tuple[str, ...], expected: dict[str, object]
) -> None:
    update = session_update(model, LiveTranscriptionSetup(languages=languages))

    transcription = update["session"]["audio"]["input"]["transcription"]
    assert transcription == {"model": model, **expected}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"type": "duration", "seconds": 4.5}, Usage(units=Decimal("4.5"), unit=Unit.AUDIO_SECOND)),
        (
            {"type": "tokens", "input_tokens": 60, "output_tokens": 9,
             "input_token_details": {"audio_tokens": 50, "text_tokens": 10}},
            Usage(input_tokens=10, input_audio_tokens=50, output_tokens=9),
        ),
        ({"type": "tokens", "input_tokens": 40}, Usage(input_audio_tokens=40)),
        ({"type": "duration"}, None),
        ("nothing", None),
    ],
)  # fmt: skip
def test_realtime_usage_is_seconds_or_audio_and_text_tokens(
    raw: object, expected: Usage | None
) -> None:
    assert realtime_usage(raw) == expected


@pytest.mark.parametrize(
    "event",
    [
        {"type": "conversation.item.input_audio_transcription.failed", "item_id": "i"},
        {"type": "error", "error": {"code": "buffer_too_small"}},
        {"type": "input_audio_buffer.speech_started"},
        {"type": "conversation.item.input_audio_transcription.delta", "delta": ""},
    ],
)
def test_events_that_carry_no_text_leave_the_session_running(event: dict[str, object]) -> None:
    assert event_of(event) == []


@pytest.mark.parametrize(
    ("reported", "floor", "expected"),
    [
        (Usage(units=Decimal(5), unit=Unit.AUDIO_SECOND),
         Usage(units=Decimal(3), unit=Unit.AUDIO_SECOND), None),
        (Usage(units=Decimal(1), unit=Unit.AUDIO_SECOND),
         Usage(units=Decimal(3), unit=Unit.AUDIO_SECOND),
         Usage(units=Decimal(2), unit=Unit.AUDIO_SECOND)),
        (Usage(input_audio_tokens=30), Usage(input_audio_tokens=100), Usage(input_audio_tokens=70)),
        (Usage(input_audio_tokens=300), Usage(input_audio_tokens=100), None),
    ],
)  # fmt: skip
def test_the_floor_adds_only_what_was_not_reported(
    reported: Usage, floor: Usage, expected: Usage | None
) -> None:
    assert shortfall(reported, floor) == expected


@pytest.mark.parametrize(
    ("code", "message", "failure"),
    [
        (1011, "RESOURCE_EXHAUSTED: quota", AiFailure.RATE_LIMITED),
        (1008, "models/x is not found", AiFailure.MODEL_UNAVAILABLE),
        (1011, "internal error", AiFailure.PROVIDER_ERROR),
    ],
)
def test_a_closed_gemini_socket_says_why(code: int, message: str, failure: AiFailure) -> None:
    error = errors.APIError(code, {"error": {"message": message, "status": ""}})

    assert failure_of(error) is failure


def test_a_translation_model_gets_no_instruction_voice_or_tools() -> None:
    config = live_config(NativeTranslationSetup("pl", echo_target_language=True))

    assert config.translation_config is not None
    assert config.translation_config.target_language_code == "pl"
    assert (config.system_instruction, config.speech_config, config.tools) == (None, None, None)


def test_an_interpreter_without_tools_declares_none() -> None:
    config = live_config(VoiceSetup("Interpret into Polish.", "Orus", silence_ms=300))

    assert config.translation_config is None
    assert config.tools is None
    assert config.realtime_input_config is not None


@pytest.mark.parametrize(
    "build",
    [
        lambda: VoiceSetup(" ", "Zephyr"),
        lambda: VoiceSetup("Speak.", "Zephyr", silence_ms=50),
        lambda: LiveTranscriptionSetup(silence_ms=5000),
    ],
)
def test_a_live_setup_out_of_bounds_is_refused(build: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match=r"\w"):
        build()
