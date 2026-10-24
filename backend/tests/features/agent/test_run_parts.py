"""The parts a run is made of, each on its own: log, reader, fleet, lease, stream (step 5a)."""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from shosai.core.ai.results import ChatDelta
from shosai.features.agent.application.model_stream import (
    AnswerBuffer,
    ModelStalledError,
    Pace,
    stream_answer,
)
from shosai.features.agent.domain.stream import EventKind, StreamEvent
from shosai.features.agent.infrastructure.fleet import Admission, Fleet
from shosai.features.agent.infrastructure.log_tail import LogTail, Silence
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases

DELTA = EventKind.TEXT_DELTA


def delta(seq: int, text: str = "x") -> StreamEvent:
    """A piece of an answer with its number."""
    return StreamEvent(seq, DELTA, {"text": text})


def end(seq: int) -> StreamEvent:
    """A run's end with its number."""
    return StreamEvent(seq, EventKind.RUN_FAILED, {"code": "failed"})


async def test_the_log_keeps_events_in_their_numbers_and_refuses_a_step_back(
    valkey: Redis,
) -> None:
    log, run = RunLog(valkey), uuid.uuid4()

    await log.append(run, (delta(1, "a"), delta(2, "b")))
    await log.append(run, (delta(3, "c"),))
    with pytest.raises(ResponseError):
        await log.append(run, (delta(2, "again"),))

    assert [event.seq for event in await log.after(run, 1)] == [2, 3]
    assert await log.last(run) == delta(3, "c")
    assert await log.kept(run)
    assert await log.last(uuid.uuid4()) is None


async def test_two_followers_get_every_event_once_and_a_new_one_is_woken(valkey: Redis) -> None:
    log, run = RunLog(valkey), uuid.uuid4()
    tail = LogTail(valkey, log)
    await log.append(run, (delta(1),))

    async def collect(after: int) -> list[int]:
        return [event.seq async for event in tail.follow(run, after)]

    try:
        first = asyncio.create_task(collect(0))
        await asyncio.sleep(0.2)
        second = asyncio.create_task(collect(1))
        await asyncio.sleep(0.1)
        await log.append(run, (delta(2),))
        await log.append(run, (end(3),))
        got = await asyncio.wait_for(asyncio.gather(first, second), 5)
    finally:
        await tail.close()

    assert list(got) == [[1, 2, 3], [2, 3]]


async def test_a_silent_follower_asks_and_may_end_with_what_it_is_told(valkey: Redis) -> None:
    log, run = RunLog(valkey), uuid.uuid4()
    tail = LogTail(valkey, log)
    await log.append(run, (delta(1),))
    asked: list[int] = []

    async def told(seq: int) -> StreamEvent | None:
        asked.append(seq)
        return end(seq + 1) if len(asked) > 1 else None

    silence = Silence(timedelta(milliseconds=200), told)
    try:
        got = [e.seq async for e in tail.follow(run, 0, silence)]
    finally:
        await tail.close()

    assert (got, asked) == ([1, 2], [1, 1])


async def test_the_fleet_admits_two_runs_a_person_and_48_a_worker(valkey: Redis) -> None:
    fleet = Fleet(valkey)
    person, other = uuid.uuid4(), uuid.uuid4()

    nobody = await fleet.admit(person, uuid.uuid4())
    await fleet.alive("worker-1")
    runs = [await fleet.admit(person, uuid.uuid4()) for _ in range(3)]
    crowd = [await fleet.admit(uuid.uuid4(), uuid.uuid4()) for _ in range(47)]
    released = uuid.uuid4()
    await fleet.release(person, released)
    await fleet.gone("worker-1")
    after_gone = await fleet.admit(other, uuid.uuid4())

    assert nobody is Admission.AGENT_BUSY
    assert runs == [Admission.ADMITTED, Admission.ADMITTED, Admission.TOO_MANY_RUNS]
    assert crowd[:46] == [Admission.ADMITTED] * 46
    assert crowd[46] is Admission.AGENT_BUSY
    assert after_gone is Admission.AGENT_BUSY


async def test_a_lease_is_renewed_and_freed_only_by_its_run(valkey: Redis) -> None:
    leases = ThreadLeases(valkey)
    thread, run, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    taken, twice = await leases.take(thread, run), await leases.take(thread, other)
    lost = await leases.renew([(thread, run), (thread, other)])
    await leases.release(thread, other)
    holder = await leases.holder(thread)
    await leases.ask_to_stop(run)
    asked = await leases.stops_asked([run, other])
    await leases.release(thread, run)

    assert (taken, twice, lost, holder, asked) == (True, False, {other}, run, {run})
    assert await leases.holder(thread) is None


async def pieces(*items: ChatDelta | float) -> AsyncIterator[ChatDelta]:
    """A model's stream: deltas, with pauses (seconds) between them."""
    for item in items:
        if isinstance(item, float):
            await asyncio.sleep(item)
        else:
            yield item


async def test_text_is_written_in_windows_and_a_silent_model_stalls() -> None:
    written: list[str] = []
    silent: list[str] = []

    async def write(text: str) -> None:
        written.append(text)

    async def write_silent(text: str) -> None:
        silent.append(text)

    pace = Pace(flush=timedelta(milliseconds=50), stall=timedelta(milliseconds=300))
    answer = await stream_answer(
        pieces(
            ChatDelta("a"), ChatDelta("b"), 0.12, ChatDelta("c"), ChatDelta(finish_reason="stop")
        ),
        AnswerBuffer(write, time.monotonic()),
        pace,
    )
    stalled = AnswerBuffer(write_silent, time.monotonic())
    with pytest.raises(ModelStalledError):
        await stream_answer(pieces(ChatDelta("d"), 1.0, ChatDelta("e")), stalled, pace)

    assert (answer.text, answer.finish_reason) == ("abc", "stop")
    assert written == ["ab", "c"]
    assert answer.first_token_ms is not None
    assert (stalled.text, silent) == ("d", ["d"])


async def test_a_failing_stream_raises_its_error_after_its_text() -> None:
    async def failing() -> AsyncIterator[ChatDelta]:
        yield ChatDelta("partial")
        raise RuntimeError

    written: list[str] = []

    async def write(text: str) -> None:
        written.append(text)

    buffer = AnswerBuffer(write, time.monotonic())
    with pytest.raises(RuntimeError):
        await stream_answer(failing(), buffer, Pace(flush=timedelta(milliseconds=10)))

    assert buffer.text == "partial"
