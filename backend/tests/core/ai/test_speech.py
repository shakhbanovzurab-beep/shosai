"""Recordings to text through OpenRouter, with their speakers when asked (ADR 0073)."""

import base64
from decimal import Decimal

import httpx
import pytest

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import AudioFile, TranscriptionRequest
from shosai.core.kernel.homes import Home
from tests.core.ai.bench import ai_bench, context, set_prices
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

AUDIO = AudioFile(b"OggS-probe-audio", "audio/webm;codecs=opus", duration_seconds=90.5)
TOKEN_MODEL = ModelRef(Provider.OPENROUTER, "probe/transcribe")
SECONDS_MODEL = ModelRef(Provider.OPENROUTER, "probe/whisper")
SCRIBE = ModelRef(Provider.OPENROUTER, "elevenlabs/scribe-v2")


async def rows(run_slot: RunSlot) -> list[dict[str, object]]:
    """Cost rows of the EU home."""
    found = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT provider, model, kind, outcome, units, unit, cost_usd, cost_source, "
        "input_tokens, output_tokens FROM provider_costs ORDER BY created_at",
    )
    return [dict(row) for row in found]


async def test_a_recording_goes_as_base64_and_its_reported_cost_is_recorded(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await set_prices(
        homes.transactions, TOKEN_MODEL, input_token="0.0000025", output_token="0.00001"
    )
    bench = ai_bench(homes.transactions)
    used = {"seconds": 90.5, "input_tokens": 830, "output_tokens": 120, "cost": 0.0033}
    bench.openrouter.answer(
        "audio/transcriptions", httpx.Response(200, json={"text": " Hello. ", "usage": used})
    )

    transcript = await bench.providers.transcribe(
        context("upload:7"), ModelRoute(TOKEN_MODEL), TranscriptionRequest(AUDIO, language="en")
    )

    [body] = bench.openrouter.bodies("audio/transcriptions")
    [row] = await rows(run_slot)
    assert (transcript.text, transcript.segments, transcript.language) == ("Hello.", (), "en")
    assert body["input_audio"] == {
        "data": base64.b64encode(AUDIO.data).decode("ascii"), "format": "webm",
    }  # fmt: skip
    assert (body["response_format"], body["language"], body["temperature"]) == ("json", "en", 0)
    assert (row["kind"], row["cost_usd"], row["cost_source"]) == (
        "transcribe", Decimal("0.0033"), "reported",
    )  # fmt: skip
    assert (row["units"], row["unit"], row["input_tokens"]) == (
        Decimal("90.500"), "audio_second", 830,
    )  # fmt: skip


async def test_timed_segments_come_back_when_asked(homes: DatabaseAccess) -> None:
    await set_prices(homes.transactions, SECONDS_MODEL, audio_second="0.0001")
    bench = ai_bench(homes.transactions)
    segments = [
        {"start": 0.0, "end": 1.25, "text": " Hello."},
        {"start": 1.25, "end": 2.5, "text": "Again.", "speaker": 1},
    ]
    answer = {"text": "Hello. Again.", "language": "english", "segments": segments,
              "usage": {"seconds": 2.5, "cost": 0.00025}}  # fmt: skip
    bench.openrouter.answer("audio/transcriptions", httpx.Response(200, json=answer))

    transcript = await bench.providers.transcribe(
        context(), ModelRoute(SECONDS_MODEL), TranscriptionRequest(AUDIO, timestamps=True)
    )

    [body] = bench.openrouter.bodies("audio/transcriptions")
    assert (body["response_format"], body["timestamp_granularities"]) == (
        "verbose_json", ["segment"],
    )  # fmt: skip
    assert [(s.start_ms, s.end_ms, s.text, s.speaker) for s in transcript.segments] == [
        (0, 1250, "Hello.", None), (1250, 2500, "Again.", 1),
    ]  # fmt: skip
    assert transcript.language == "english"


@pytest.mark.parametrize(
    "prices",
    [{"input_token": "0.0000025", "output_token": "0.00001"}, {"audio_second": "0.0001"}],
)
async def test_a_speech_model_is_priced_by_tokens_or_by_seconds(
    homes: DatabaseAccess, prices: dict[str, str]
) -> None:
    await set_prices(homes.transactions, TOKEN_MODEL, **prices)
    bench = ai_bench(homes.transactions)
    bench.openrouter.answer(
        "audio/transcriptions", httpx.Response(200, json={"text": "Hi.", "usage": {"cost": 0}})
    )

    transcript = await bench.providers.transcribe(
        context(), ModelRoute(TOKEN_MODEL), TranscriptionRequest(AUDIO)
    )

    assert transcript.text == "Hi."


async def test_a_speech_model_priced_by_half_its_tokens_is_refused(homes: DatabaseAccess) -> None:
    await set_prices(homes.transactions, TOKEN_MODEL, input_token="0.0000025")
    bench = ai_bench(homes.transactions)

    with pytest.raises(AiCallError) as refused:
        await bench.providers.transcribe(
            context(), ModelRoute(TOKEN_MODEL), TranscriptionRequest(AUDIO)
        )

    assert refused.value.failure is AiFailure.MODEL_UNPRICED
    assert bench.openrouter.requests == []


async def test_an_unknown_recording_format_is_refused_before_it_is_sent(
    homes: DatabaseAccess,
) -> None:
    await set_prices(homes.transactions, SECONDS_MODEL, audio_second="0.0001")
    bench = ai_bench(homes.transactions)
    odd = AudioFile(b"probe", "audio/x-unknown", duration_seconds=1)

    with pytest.raises(AiCallError) as refused:
        await bench.providers.transcribe(
            context(), ModelRoute(SECONDS_MODEL), TranscriptionRequest(odd)
        )

    assert refused.value.failure is AiFailure.CONTENT_REFUSED
    assert bench.openrouter.requests == []


async def test_speakers_are_asked_of_the_provider_and_read_from_the_words(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    await set_prices(homes.transactions, SCRIBE, audio_second="0.0000611111")
    bench = ai_bench(homes.transactions)
    words = [
        {"word": "Привет,", "start": 0.1, "end": 0.5, "speaker": 0},
        {"word": "коллеги.", "start": 0.55, "end": 1.0, "speaker": 0},
        {"word": "Здравствуйте.", "start": 1.2, "end": 1.9, "speaker": 1},
    ]
    answer = {"text": "Привет, коллеги. Здравствуйте.", "language": "rus", "words": words,
              "segments": [{"start": 0.0, "end": 1.9, "text": "Привет, коллеги. Здравствуйте."}],
              "usage": {"seconds": 1.9, "cost": 0.000116}}  # fmt: skip
    bench.openrouter.answer("audio/transcriptions", httpx.Response(200, json=answer))

    transcript = await bench.providers.transcribe(
        context("notes:7:transcribe:0"), ModelRoute(SCRIBE),
        TranscriptionRequest(AUDIO, timestamps=True, speakers=True),
    )  # fmt: skip

    [body] = bench.openrouter.bodies("audio/transcriptions")
    [row] = await rows(run_slot)
    assert (body["response_format"], body["timestamp_granularities"]) == (
        "verbose_json", ["segment", "word"],
    )  # fmt: skip
    assert body["provider"] == {
        "options": {"elevenlabs": {"diarize": True, "tag_audio_events": False}}
    }
    assert [(s.start_ms, s.end_ms, s.text, s.speaker) for s in transcript.segments] == [
        (100, 1000, "Привет, коллеги.", 0), (1200, 1900, "Здравствуйте.", 1),
    ]  # fmt: skip
    assert (row["kind"], row["cost_usd"], row["cost_source"]) == (
        "transcribe", Decimal("0.000116"), "reported",
    )  # fmt: skip


async def test_a_model_without_speakers_answers_its_segments_unmarked(
    homes: DatabaseAccess,
) -> None:
    await set_prices(homes.transactions, SECONDS_MODEL, audio_second="0.0001")
    bench = ai_bench(homes.transactions)
    answer = {"text": "Hello.", "segments": [{"start": 0.0, "end": 1.0, "text": "Hello."}],
              "usage": {"seconds": 1.0, "cost": 0.0001}}  # fmt: skip
    bench.openrouter.answer("audio/transcriptions", httpx.Response(200, json=answer))

    transcript = await bench.providers.transcribe(
        context(), ModelRoute(SECONDS_MODEL), TranscriptionRequest(AUDIO, speakers=True)
    )

    assert [(s.start_ms, s.end_ms, s.text, s.speaker) for s in transcript.segments] == [
        (0, 1000, "Hello.", None)
    ]
