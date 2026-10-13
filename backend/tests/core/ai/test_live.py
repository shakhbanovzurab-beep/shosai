"""Live sessions against a local provider server: one row per minute, a broken socket recorded."""

from collections.abc import Callable
from decimal import Decimal

import pytest

from shosai.core.ai.adapters.gemini_live import GeminiLive, gemini_client
from shosai.core.ai.adapters.openai_realtime import OpenAiRealtime
from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.requests import (
    LiveTranscriptionSetup,
    NativeTranslationSetup,
    ToolSchema,
    VoiceSetup,
)
from shosai.core.ai.results import (
    LiveAudio,
    LiveChannel,
    LiveEnd,
    LiveEvent,
    LiveText,
    LiveToolCall,
)
from shosai.core.kernel.homes import Home
from tests.core.ai.bench import AiBench, Doubles, ai_bench, context, set_prices
from tests.core.ai.live_scenarios import Reader, gemini_scenario, openai_scenario
from tests.doubles.live_server import LiveServer, client_tls, live_server
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

TRANSCRIBER = ModelRef(Provider.OPENAI, "gpt-live-transcribe")
TRANSLATOR = ModelRef(Provider.GOOGLE, "gemini-3.5-live-translate-preview")
VOICE = ModelRef(Provider.GOOGLE, "gemini-3.8-live")
SECOND_AT_24K = b"\x00\x00" * 24_000
SECOND_AT_16K = b"\x00\x00" * 16_000


async def rows(run_slot: RunSlot) -> list[dict[str, object]]:
    """Cost rows of the EU home in the order of their minutes."""
    found = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT effect_key, kind, units, input_tokens, input_audio_tokens, output_tokens, "
        "output_audio_tokens, cost_usd FROM provider_costs ORDER BY created_at",
    )
    return [dict(row) for row in found]


def finals(events: list[LiveEvent]) -> list[str]:
    """Texts of the finished items."""
    return [e.text for e in events if isinstance(e, LiveText) and e.final]


def heard(count: int) -> Callable[[list[LiveEvent]], bool]:
    """Whether `count` items were finished."""
    return lambda events: len(finals(events)) == count


async def transcribing(homes: DatabaseAccess, server: LiveServer) -> AiBench:
    """A bench with OpenAI Realtime at the local server and the model priced per second."""
    await set_prices(homes.transactions, TRANSCRIBER, audio_second="0.000283333333")
    realtime = OpenAiRealtime("probe-key", server.url + "/v1/realtime", tls=client_tls())
    return ai_bench(homes.transactions, doubles=Doubles(realtime=realtime))


async def speaking(homes: DatabaseAccess, server: LiveServer) -> AiBench:
    """A bench with Gemini Live at the local server and both of its models priced."""
    await set_prices(
        homes.transactions, TRANSLATOR,
        input_audio_token="0.0000035", output_audio_token="0.000021",
    )  # fmt: skip
    await set_prices(
        homes.transactions, VOICE, input_token="0.00000075", input_audio_token="0.000003",
        output_token="0.0000045", output_audio_token="0.000012",
    )  # fmt: skip
    base_url = server.url.replace("wss://", "https://")
    gemini = GeminiLive(gemini_client("probe-key", base_url, tls=client_tls()))
    return ai_bench(homes.transactions, doubles=Doubles(gemini=gemini))


async def test_a_three_minute_transcription_writes_a_row_per_minute(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    async with live_server(openai_scenario(seconds=60.0)) as server:
        bench = await transcribing(homes, server)
        setup = LiveTranscriptionSetup(languages=("ru", "en"))
        async with bench.providers.open_transcription_stream(
            context("stream:m1"), TRANSCRIBER, setup
        ) as session:
            reader = Reader().start(session)
            for minute in range(1, 4):
                await session.send_audio(SECOND_AT_24K)
                await session.end_turn()
                await reader.until(heard(minute))
                bench.clock.now += 60
        events = await reader.finished()

    [update] = server.of_type("session.update")
    path, headers = server.handshakes[0]
    audio = update["session"]["audio"]["input"]
    assert finals(events) == ["Hello 1.", "Hello 2.", "Hello 3."]
    assert events[-1] == LiveEnd(None)
    assert (path, headers["Authorization"]) == ("/v1/realtime", "Bearer probe-key")
    assert audio["format"] == {"type": "audio/pcm", "rate": 24_000}
    assert audio["transcription"] == {"model": "gpt-live-transcribe", "languages": ["ru", "en"]}
    found = await rows(run_slot)
    assert [row["effect_key"] for row in found] == ["stream:m1:0", "stream:m1:1", "stream:m1:2"]
    assert {(row["kind"], row["units"]) for row in found} == {("live_transcription", Decimal(60))}


async def test_a_dropped_socket_ends_the_session_and_its_audio_is_still_billed(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    async with live_server(openai_scenario(seconds=0.5, drop_after=1)) as server:
        bench = await transcribing(homes, server)
        async with bench.providers.open_transcription_stream(
            context("stream:m2"), TRANSCRIBER, LiveTranscriptionSetup()
        ) as session:
            reader = Reader().start(session)
            await session.send_audio(SECOND_AT_24K * 2)
            await session.end_turn()
            events = await reader.finished()

    [row] = await rows(run_slot)
    assert events[-1] == LiveEnd(AiFailure.PROVIDER_ERROR)
    # Сообщено 0.5 с, ушло 2 с звука: строка не меньше отправленного.
    assert (row["effect_key"], row["units"]) == ("stream:m2:0", Decimal("2.000"))


@pytest.mark.parametrize(
    ("status", "failure", "attempts"),
    [(429, AiFailure.RATE_LIMITED, 1), (500, AiFailure.PROVIDER_ERROR, 2)],
)
async def test_a_refused_connection_is_retried_once_only_when_transient(
    homes: DatabaseAccess, run_slot: RunSlot, status: int, failure: AiFailure, attempts: int
) -> None:
    async with live_server(openai_scenario()) as server:
        server.refuse_with = status
        bench = await transcribing(homes, server)
        with pytest.raises(AiCallError) as refused:
            async with bench.providers.open_transcription_stream(
                context(), TRANSCRIBER, LiveTranscriptionSetup()
            ):
                pytest.fail("сессия не должна открыться")

    assert refused.value.failure is failure
    assert len(server.handshakes) == attempts
    assert await rows(run_slot) == []


async def test_a_session_whose_setup_is_refused_does_not_open(homes: DatabaseAccess) -> None:
    async with live_server(openai_scenario(refuse_setup=True)) as server:
        bench = await transcribing(homes, server)
        with pytest.raises(AiCallError) as refused:
            async with bench.providers.open_transcription_stream(
                context(), TRANSCRIBER, LiveTranscriptionSetup()
            ):
                pytest.fail("сессия не должна открыться")

    assert refused.value.failure is AiFailure.PROVIDER_ERROR


async def test_a_translation_streams_texts_and_speech_and_meters_audio_tokens(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    async with live_server(gemini_scenario()) as server:
        bench = await speaking(homes, server)
        async with bench.providers.open_translation_stream(
            context("call:t1"), TRANSLATOR, NativeTranslationSetup("pl")
        ) as session:
            reader = Reader().start(session)
            await session.send_audio(SECOND_AT_16K)
            await reader.until(lambda events: any(isinstance(e, LiveAudio) for e in events))
        events = await reader.finished()

    [setup] = server.keyed("setup")
    [audio] = server.keyed("realtimeInput")
    texts = [(e.channel, e.text, e.final) for e in events if isinstance(e, LiveText)]
    [row] = await rows(run_slot)
    assert setup["model"] == "models/gemini-3.5-live-translate-preview"
    assert setup["generationConfig"]["translationConfig"] == {
        "targetLanguageCode": "pl", "echoTargetLanguage": False,
    }  # fmt: skip
    assert "inputAudioTranscription" in setup
    assert audio["audio"]["mime_type"] == "audio/pcm;rate=16000"
    assert texts == [(LiveChannel.INPUT, "Привет", True), (LiveChannel.OUTPUT, "Hello", True)]
    assert [e.sample_rate for e in events if isinstance(e, LiveAudio)] == [24_000]
    assert (row["kind"], row["input_audio_tokens"], row["output_audio_tokens"]) == (
        "live_translation", 50, 50,
    )  # fmt: skip
    assert row["cost_usd"] == Decimal("0.0012250000")


async def test_a_voice_session_hands_tool_calls_over_and_returns_their_results(
    homes: DatabaseAccess,
) -> None:
    tool = ToolSchema("consult", "Ask Leo a question.", {"type": "object"})
    setup = VoiceSetup("You are a careful assistant.", "Zephyr", tools=(tool,))
    async with live_server(gemini_scenario(tool_call=True)) as server:
        bench = await speaking(homes, server)
        async with bench.providers.open_voice_session(context(), VOICE, setup) as session:
            reader = Reader().start(session)
            await session.send_audio(SECOND_AT_16K)
            await reader.until(lambda events: any(isinstance(e, LiveToolCall) for e in events))
            [call] = [e for e in reader.events if isinstance(e, LiveToolCall)]
            await session.send_tool_result(call, '{"answer": "Tomorrow."}')
            await server.until(lambda seen: bool(seen.keyed("toolResponse")))
        await reader.finished()

    [sent] = server.keyed("setup")
    [response] = server.keyed("toolResponse")
    assert (call.call_id, call.name, call.arguments) == (
        "call-1",
        "consult",
        '{"question": "When?"}',
    )
    assert sent["systemInstruction"]["parts"] == [{"text": "You are a careful assistant."}]
    assert sent["tools"][0]["functionDeclarations"][0]["name"] == "consult"
    assert response["functionResponses"][0]["id"] == "call-1"


async def test_a_broken_live_session_is_billed_at_its_audio_floor(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    async with live_server(gemini_scenario(drop=True)) as server:
        bench = await speaking(homes, server)
        async with bench.providers.open_translation_stream(
            context("call:t2"), TRANSLATOR, NativeTranslationSetup("de")
        ) as session:
            reader = Reader().start(session)
            await session.send_audio(SECOND_AT_16K * 4)
            events = await reader.finished()

    [row] = await rows(run_slot)
    assert events[-1] == LiveEnd(AiFailure.PROVIDER_ERROR)
    # Сообщено 50 токенов звука, ушло 4 с по 25 токенов: учтено 100.
    assert row["input_audio_tokens"] == 100


@pytest.mark.parametrize("model", [TRANSLATOR, ModelRef(Provider.OPENROUTER, "probe/translate")])
async def test_without_a_client_for_the_model_a_session_is_refused(
    homes: DatabaseAccess, model: ModelRef
) -> None:
    bench = ai_bench(homes.transactions)

    with pytest.raises(AiCallError) as refused:
        bench.providers.open_translation_stream(context(), model, NativeTranslationSetup("en"))

    assert refused.value.failure is AiFailure.MODEL_UNAVAILABLE


async def test_an_unpriced_live_model_is_refused_before_it_connects(
    homes: DatabaseAccess,
) -> None:
    async with live_server(gemini_scenario()) as server:
        bench = await speaking(homes, server)
        unpriced = ModelRef(Provider.GOOGLE, "gemini-probe-live")
        with pytest.raises(AiCallError) as refused:
            async with bench.providers.open_translation_stream(
                context(), unpriced, NativeTranslationSetup("en")
            ):
                pytest.fail("сессия не должна открыться")

    assert refused.value.failure is AiFailure.MODEL_UNPRICED
    assert server.handshakes == []
