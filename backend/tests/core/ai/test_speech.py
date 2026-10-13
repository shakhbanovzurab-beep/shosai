"""Recordings to text through OpenRouter and to speaker turns through pyannote."""

import base64
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import AudioFile, DiarizationRequest, TranscriptionRequest
from shosai.core.kernel.homes import Home
from tests.core.ai.bench import AiBench, ai_bench, context, set_prices
from tests.doubles.pyannote import UPLOAD_LINK
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

AUDIO = AudioFile(b"OggS-probe-audio", "audio/webm;codecs=opus", duration_seconds=90.5)
TOKEN_MODEL = ModelRef(Provider.OPENROUTER, "probe/transcribe")
SECONDS_MODEL = ModelRef(Provider.OPENROUTER, "probe/whisper")
DIARIZER = ModelRef(Provider.PYANNOTE, "precision-2")
PER_SECOND = "0.00003"


async def rows(run_slot: RunSlot) -> list[dict[str, object]]:
    """Cost rows of the EU home."""
    found = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT provider, model, kind, outcome, units, unit, cost_usd, cost_source, "
        "input_tokens, output_tokens FROM provider_costs ORDER BY created_at",
    )
    return [dict(row) for row in found]


async def diarizing_bench(homes: DatabaseAccess) -> AiBench:
    """A bench whose diarization model has its price per second."""
    await set_prices(homes.transactions, DIARIZER, audio_second=PER_SECOND)
    return ai_bench(homes.transactions)


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


async def test_speakers_are_numbered_by_first_appearance_and_the_seconds_are_priced(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await diarizing_bench(homes)
    bench.pyannote.turns = [
        {"speaker": "SPEAKER_07", "start": 0.5, "end": 2.0},
        {"speaker": "SPEAKER_02", "start": 2.0, "end": 3.5},
        {"speaker": "SPEAKER_07", "start": 3.5, "end": 4.0},
    ]

    result = await bench.providers.diarize(
        context("meeting:9:diarize"), ModelRoute(DIARIZER), DiarizationRequest(AUDIO, speakers=2)
    )

    [upload] = bench.pyannote.sent("PUT", "/upload/probe")
    media = bench.pyannote.body("POST", "media/input")["url"]
    [row] = await rows(run_slot)
    assert [(t.start_ms, t.end_ms, t.speaker) for t in result.turns] == [
        (500, 2000, 0), (2000, 3500, 1), (3500, 4000, 0),
    ]  # fmt: skip
    assert str(upload.url) == UPLOAD_LINK
    assert "authorization" not in upload.headers
    assert upload.content == AUDIO.data
    assert media.startswith("media://shosai/")
    assert media.endswith(".webm")
    assert bench.pyannote.body("POST", "diarize") == {
        "url": media, "model": "precision-2", "numSpeakers": 2,
    }  # fmt: skip
    assert (row["kind"], row["outcome"], row["units"], row["unit"]) == (
        "diarize", "ok", Decimal("90.500"), "audio_second",
    )  # fmt: skip
    assert (row["cost_usd"], row["cost_source"]) == (Decimal("0.0027150000"), "priced")


@pytest.mark.parametrize(
    ("statuses", "failure"),
    [
        (["running", "failed"], AiFailure.PROVIDER_ERROR),
        (["running"], AiFailure.DEADLINE_EXCEEDED),
    ],
)
async def test_a_job_that_fails_after_the_upload_is_still_recorded(
    homes: DatabaseAccess, run_slot: RunSlot, statuses: list[str], failure: AiFailure
) -> None:
    bench = await diarizing_bench(homes)
    bench.pyannote.statuses = statuses

    with pytest.raises(AiCallError) as failed:
        await bench.providers.diarize(
            context(deadline=timedelta(minutes=5)), ModelRoute(DIARIZER), DiarizationRequest(AUDIO)
        )

    [row] = await rows(run_slot)
    assert failed.value.failure is failure
    assert (row["kind"], row["outcome"], row["units"]) == ("diarize", "failed", Decimal("90.500"))


async def test_a_job_never_started_writes_no_row(homes: DatabaseAccess, run_slot: RunSlot) -> None:
    bench = await diarizing_bench(homes)
    bench.pyannote.failing["diarize"] = 402

    with pytest.raises(AiCallError) as failed:
        await bench.providers.diarize(context(), ModelRoute(DIARIZER), DiarizationRequest(AUDIO))

    assert failed.value.failure is AiFailure.PROVIDER_ERROR
    assert await rows(run_slot) == []


async def test_without_its_key_diarization_is_refused(homes: DatabaseAccess) -> None:
    await set_prices(homes.transactions, DIARIZER, audio_second=PER_SECOND)
    bench = ai_bench(homes.transactions, enabled=False)

    with pytest.raises(AiCallError) as refused:
        await bench.providers.diarize(context(), ModelRoute(DIARIZER), DiarizationRequest(AUDIO))

    assert refused.value.failure is AiFailure.MODEL_UNAVAILABLE
    assert bench.sample("shosai_ai_calls_refused_total", kind="diarize", code="model_unavailable")


async def test_a_model_of_another_provider_is_not_sent_to_the_diarizer(
    homes: DatabaseAccess,
) -> None:
    bench = await diarizing_bench(homes)

    with pytest.raises(AiCallError) as refused:
        await bench.providers.diarize(context(), ModelRoute(TOKEN_MODEL), DiarizationRequest(AUDIO))

    assert refused.value.failure is AiFailure.MODEL_UNAVAILABLE
    assert bench.pyannote.requests == []
