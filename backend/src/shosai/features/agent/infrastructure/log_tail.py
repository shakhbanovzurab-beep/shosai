"""Following run logs in an API process: one blocked `XREAD` for every stream it serves (AG-D12).

A follower first reads what the log already holds, then waits for the rest from the process's
one reader, which blocks on the logs of every run followed here and on the process's own wake
stream: a new follower writes to the wake stream, so the reader picks the new log up at once
instead of after its block. The block is two seconds, under the managed Valkey's cut of a
blocking read (draft lesson). The reader starts with the process's first follower and runs
until the process stops. Each follower gets only events after the last one it got, so two
tabs of one run share the reads and neither sees an event twice. Followers are kept by their
log's key, named once: a read hands its events to the followers of each log it got, never
scanning the others (agent step 17: the scan named every followed log's key on every read). A
failing read is logged and retried after a pause; followers keep waiting and their streams keep
their heartbeats.
"""

import asyncio
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.typing import KeyT, StreamIdT

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.features.agent.domain.stream import StreamEvent, closes_stream
from shosai.features.agent.infrastructure.run_keys import log_key, wake_key
from shosai.features.agent.infrastructure.run_log import RunLog, entry_id, event_of, streams_of

BLOCK: Final = timedelta(seconds=2)
OUTAGE_PAUSE: Final = timedelta(seconds=1)
WAKE_TTL: Final = timedelta(minutes=10)
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Silence:
    """What a follower does after `after` without an event: `ask` may give the end the run's
    record holds when its log never got it."""

    after: timedelta
    ask: Callable[[int], Awaitable[StreamEvent | None]]


@dataclass(eq=False)
class Follower:
    """One stream of one run: the last number it got and the events waiting for it."""

    run_id: UUID
    seq: int
    events: asyncio.Queue[StreamEvent] = field(default_factory=asyncio.Queue)
    key: str = field(init=False)

    def __post_init__(self) -> None:
        self.key = log_key(self.run_id)


class LogTail:
    """The process's reader of run logs and the followers it serves."""

    def __init__(self, valkey: Redis, run_log: RunLog) -> None:
        self._valkey = valkey
        self._log = run_log
        self._wake = wake_key(secrets.token_hex(8))
        self._wake_seen = "0-0"
        self._followers: dict[str, set[Follower]] = {}
        self._reader: asyncio.Task[None] | None = None

    async def follow(
        self, run_id: UUID, after: int, silence: Silence | None = None
    ) -> AsyncIterator[StreamEvent]:
        """The run's events after number `after`, until its terminal event or a pause nothing
        follows yet; after each `silence.after` without one, `silence.ask` may end the stream
        with an event."""
        follower = Follower(run_id, after)
        kept = await self._log.after(run_id, after)
        for index, event in enumerate(kept):
            follower.seq = event.seq
            yield event
            if closes_stream(event, followed=index < len(kept) - 1):
                return
        self._followers.setdefault(follower.key, set()).add(follower)
        try:
            await self._wake_reader()
            while True:
                came = await self._next(follower, silence)
                if came is None:
                    continue
                yield came
                if closes_stream(came, followed=False):
                    return
        finally:
            self._forget(follower)

    @staticmethod
    async def _next(follower: Follower, silence: Silence | None) -> StreamEvent | None:
        if silence is None:
            return await follower.events.get()
        try:
            return await asyncio.wait_for(follower.events.get(), silence.after.total_seconds())
        except TimeoutError:
            ending = await silence.ask(follower.seq)
            if ending is not None:
                follower.seq = ending.seq
            return ending

    async def close(self) -> None:
        """Stop the reader; called when the process stops."""
        if self._reader is not None:
            self._reader.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader

    async def _wake_reader(self) -> None:
        if self._reader is None or self._reader.done():
            self._reader = asyncio.create_task(self._read_forever(), name="agent-log-tail")
            return
        async with self._valkey.pipeline(transaction=False) as pipeline:
            await pipeline.xadd(self._wake, {"w": "1"}, maxlen=1)
            await pipeline.expire(self._wake, WAKE_TTL)
            await pipeline.execute()

    async def _read_forever(self) -> None:
        while True:
            try:
                await self._read_once()
            except REDIS_FAILURES as error:
                log.warning(
                    "Valkey не ответил читателю журналов Leo", error_type=type(error).__name__
                )
                await asyncio.sleep(OUTAGE_PAUSE.total_seconds())
            # Сбой разбора не должен оставить подписчиков без читателя: он в журнале со стеком.
            except Exception:
                log.exception("Читатель журналов Leo споткнулся; продолжает после паузы")
                await asyncio.sleep(OUTAGE_PAUSE.total_seconds())

    def _forget(self, follower: Follower) -> None:
        followers = self._followers.get(follower.key)
        if followers is None:
            return
        followers.discard(follower)
        if not followers:
            del self._followers[follower.key]

    async def _read_once(self) -> None:
        positions: dict[KeyT, StreamIdT] = {self._wake: self._wake_seen}
        positions |= {
            key: entry_id(min(follower.seq for follower in followers))
            for key, followers in self._followers.items()
        }
        reply = await self._valkey.xread(positions, block=int(BLOCK.total_seconds() * 1000))
        for key, entries in streams_of(reply).items():
            if not entries:
                continue
            if key == self._wake:
                self._wake_seen = entries[-1][0]
                continue
            self._dispatch(key, [event_of(entry) for entry in entries])

    def _dispatch(self, key: str, events: list[StreamEvent]) -> None:
        for follower in self._followers.get(key, ()):
            for event in events:
                if event.seq > follower.seq:
                    follower.seq = event.seq
                    follower.events.put_nowait(event)
