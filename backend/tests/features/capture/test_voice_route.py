"""`WS /v1/ws/voice` end to end (LEO-voice step 5, ADR 0070): hello → speech → a tool → a
spoken answer → two messages in the thread, the minutes counted; and its refusals."""

import asyncio
import json
import uuid
from typing import Any, Final

import pytest
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.kv.locks import LockOutagePolicy
from shosai.features.agent.infrastructure.person_records import AgentSettingsRecord
from shosai.features.capture.application.voice_minutes import LOCK_TTL
from tests.features.agent.turn_bench import HOME
from tests.features.capture.voice_bench import CABINET, VoiceBench, hello
from tests.features.capture.voice_scenario import ANSWER, QUESTION
from tests.harness.connections import fetch_rows

SPEECH: Final = b"\x00\x00" * 1_600
LISTENING: Final = {"type": "state", "state": "listening"}


async def answered(client: ClientConnection) -> tuple[list[dict[str, Any]], list[bytes]]:
    """Frames and speech until Leo, having spoken, listens again."""
    frames: list[dict[str, Any]] = []
    audio: list[bytes] = []
    async with asyncio.timeout(10):
        while not (audio and frames[-1] == LISTENING):
            message = await client.recv()
            if isinstance(message, bytes):
                audio.append(message)
            else:
                frames.append(json.loads(message))
    return frames, audio


async def refusal(bench: VoiceBench, first: dict[str, Any]) -> tuple[int | None, str | None]:
    """The close code and reason a conversation that opens with this hello gets."""
    async with connect(bench.url, origin=CABINET) as client:
        await client.send(json.dumps(first))
        with pytest.raises(ConnectionClosed):
            await asyncio.wait_for(client.recv(), 10)
    return client.close_code, client.close_reason


async def test_a_spoken_question_is_answered_from_notes_and_kept_in_the_thread(
    voice_bench: VoiceBench,
) -> None:
    person = uuid.uuid4()
    async with connect(voice_bench.url, origin=CABINET) as client:
        await client.send(json.dumps(hello(person)))
        ready = json.loads(await client.recv())
        await client.send(SPEECH)
        frames, audio = await answered(client)
        await client.send(json.dumps({"type": "end"}))
        rest = [json.loads(m) async for m in client if isinstance(m, str)]

    thread = uuid.UUID(ready["thread_id"])
    connection = voice_bench.turn.connection
    messages = await fetch_rows(
        connection,
        "SELECT role, text FROM agent_messages WHERE thread_id = %s ORDER BY created_at",
        (thread,),
    )
    runs = await fetch_rows(
        connection, "SELECT channel, tool_calls FROM agent_runs WHERE thread_id = %s", (thread,)
    )
    [session] = await fetch_rows(
        connection,
        "SELECT id, end_code, ended_at FROM capture_voice_sessions WHERE user_id = %s",
        (person,),
    )
    costs = await fetch_rows(
        connection,
        "SELECT kind FROM provider_costs WHERE effect_key LIKE %s",
        (f"capture.voice:{session['id']}%",),
    )
    assert (ready["input_rate"], ready["output_rate"]) == (16_000, 24_000)
    assert {"type": "transcript", "who": "person", "text": QUESTION, "final": True} in frames
    assert {"type": "transcript", "who": "leo", "text": ANSWER, "final": True} in frames
    assert {"type": "step", "activity": "notes.search", "status": "done"} in frames
    assert audio
    assert rest == [{"type": "ended", "code": "ended"}]
    assert (client.close_code, voice_bench.turn.tools.ran) == (1000, ["budget"])
    assert [(m["role"], m["text"]) for m in messages] == [("user", QUESTION), ("assistant", ANSWER)]
    assert [(r["channel"], r["tool_calls"]) for r in runs] == [("voice", 1)]
    assert session["end_code"] == "ended"
    assert session["ended_at"] is not None
    assert {cost["kind"] for cost in costs} == {"voice"}
    instruction = json.dumps(voice_bench.gemini.received[0])
    assert "Charon" in instruction
    assert "notes__search" in instruction


async def test_a_conversation_is_refused_with_the_reason_the_cabinet_shows(
    voice_bench: VoiceBench,
) -> None:
    person = uuid.uuid4()

    wrong_protocol = await refusal(voice_bench, hello(person, v=2))
    voice_bench.allowance.limit_minutes = 0
    no_minutes = await refusal(voice_bench, hello(person))
    voice_bench.allowance.limit_minutes = 60
    async with voice_bench.locks.hold(
        f"capture.voice.{person}", ttl=LOCK_TTL, outage=LockOutagePolicy.FAIL_CLOSED
    ):
        busy = await refusal(voice_bench, hello(person))
    async with voice_bench.turn.homes.transactions.begin(TenancyScope(HOME, person)) as session:
        session.add(AgentSettingsRecord(user_id=person, voice_mode=False))
    switched_off = await refusal(voice_bench, hello(person))

    assert [wrong_protocol, no_minutes, busy, switched_off] == [
        (4400, "bad_hello"), (4402, "minutes_exhausted"), (4409, "voice_busy"),
        (4403, "voice_mode_off"),
    ]  # fmt: skip
