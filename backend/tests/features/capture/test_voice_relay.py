"""The voice relay between the cabinet and Gemini (LEO-voice step 5, ADR 0070 LV-D2, LV-D7)."""

import asyncio
import json
from datetime import timedelta

import pytest

from shosai.core.ai.errors import AiFailure
from shosai.core.ai.results import (
    LiveAudio,
    LiveChannel,
    LiveEnd,
    LiveInterrupted,
    LiveText,
    LiveToolCall,
    LiveToolsCancelled,
    LiveTurnEnd,
)
from shosai.features.capture.channels.voice_links import RelayTimes
from shosai.features.capture.channels.voice_relay import VoiceRelay
from shosai.features.capture.domain.voice import VoiceEnd
from shosai.features.capture.infrastructure.voice_texts import TOOL_FAILED
from tests.features.capture.relay_doubles import CARD, FOUND, Cabinet, Gemini, Minutes, Talk, until

SPEECH = b"\x01\x00" * 8
TICK = timedelta(milliseconds=10)
SOON = timedelta(milliseconds=60)
QUICK = RelayTimes(check_every=TICK)


def relay_of(
    talk: Talk | None = None, times: RelayTimes = QUICK, minutes: Minutes | None = None
) -> tuple[VoiceRelay, Cabinet, Gemini, Talk]:
    """A relay over doubles."""
    cabinet, gemini, talk = Cabinet(), Gemini(), talk or Talk()
    return VoiceRelay((cabinet, gemini), (talk, minutes or Minutes()), times), cabinet, gemini, talk


def heard(text: str, *, final: bool = True) -> LiveText:
    """The person's words."""
    return LiveText(text, LiveChannel.INPUT, final=final)


def said(text: str) -> LiveText:
    """Leo's words."""
    return LiveText(text, LiveChannel.OUTPUT, final=True)


async def test_a_question_a_read_and_a_spoken_answer_make_one_exchange() -> None:
    relay, cabinet, gemini, talk = relay_of()
    running = asyncio.create_task(relay.run())
    await cabinet.inbox.put(SPEECH)
    talk.gate.clear()
    await gemini.put(heard("What about the budget?"), LiveToolCall("c-1", "notes__search", "{}"))
    # Gemini заканчивает ход сразу после вызова, до ответа инструмента.
    await gemini.put(LiveTurnEnd())
    await until(lambda: talk.calls)
    talk.gate.set()
    await until(lambda: gemini.results)
    await gemini.put(said("Travel was cut."), LiveAudio(SPEECH, 24_000), LiveTurnEnd())
    await until(lambda: talk.exchanges)
    await cabinet.inbox.put(json.dumps({"type": "end"}))

    assert await running is VoiceEnd.ENDED
    assert (gemini.audio, cabinet.audio, gemini.results) == ([SPEECH], [SPEECH], [("c-1", FOUND)])
    assert cabinet.kinds() == [
        "state:listening", "transcript:person", "state:thinking", "step:running", "step:done",
        "transcript:leo", "state:speaking", "state:listening",
    ]  # fmt: skip
    [exchange] = talk.exchanges
    assert (exchange.question, exchange.answer, exchange.interrupted) == (
        "What about the budget?", "Travel was cut.", False,
    )  # fmt: skip


async def test_an_interruption_stops_the_answer_cancels_the_call_and_opens_the_next_phrase() -> (
    None
):
    talk = Talk()
    talk.gate.clear()
    relay, cabinet, gemini, _ = relay_of(talk)
    running = asyncio.create_task(relay.run())
    await gemini.put(heard("Book a room."), LiveToolCall("c-1", "tasks__create", "{}"))
    await until(lambda: talk.calls)
    await gemini.put(said("Let me"), heard("Stop,", final=False), LiveInterrupted())
    await gemini.put(LiveToolsCancelled(("c-1",)), LiveEnd(AiFailure.PROVIDER_ERROR))

    assert await running is VoiceEnd.PROVIDER
    assert gemini.results == []
    assert {"type": "interrupted"} in cabinet.sent
    assert [(e.question, e.answer, e.interrupted) for e in talk.exchanges] == [
        ("Book a room.", "Let me", True), ("Stop,", "", True),
    ]  # fmt: skip


async def test_a_card_reaches_the_cabinet_and_a_failed_call_still_answers_the_model() -> None:
    talk = Talk()
    relay, cabinet, gemini, _ = relay_of(talk)
    running = asyncio.create_task(relay.run())
    await gemini.put(LiveToolCall("c-1", "tasks__create", "{}"))
    await until(lambda: gemini.results)
    talk.fail = True
    await gemini.put(LiveToolCall("c-2", "notes__search", "{}"))
    await until(lambda: len(gemini.results) == 2)
    await cabinet.inbox.put(None)

    assert await running is VoiceEnd.ENDED
    assert {"type": "action.proposed", "action_id": str(CARD)} in cabinet.sent
    assert gemini.results == [("c-1", FOUND), ("c-2", TOOL_FAILED)]


@pytest.mark.parametrize(
    ("times", "left", "end"),
    [
        (RelayTimes(idle=SOON, check_every=TICK), 30, VoiceEnd.IDLE),
        (RelayTimes(longest=SOON, check_every=TICK), 30, VoiceEnd.TIME_LIMIT),
        (RelayTimes(minute=SOON, check_every=TICK), 2, VoiceEnd.MINUTES),
    ],
)
async def test_a_limit_ends_the_conversation(times: RelayTimes, left: int, end: VoiceEnd) -> None:
    relay, _, _, talk = relay_of(times=times, minutes=Minutes(left=left))

    assert await relay.run() is end
    assert talk.exchanges == []


async def test_the_drain_ends_it_and_what_was_said_is_kept_as_interrupted() -> None:
    relay, cabinet, gemini, talk = relay_of()
    running = asyncio.create_task(relay.run())
    await gemini.put(heard("Tell me"), said("Of"))
    await until(lambda: len(cabinet.sent) == 3)
    cabinet.stopping.set()

    assert await running is VoiceEnd.SHUTDOWN
    assert [(e.question, e.answer, e.interrupted) for e in talk.exchanges] == [
        ("Tell me", "Of", True)
    ]
