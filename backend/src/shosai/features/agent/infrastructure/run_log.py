"""A run's event log: a Valkey stream any API process streams and resumes from (ADR 0032, AG-D12).

An event's stream id is `0-<its number>`, so the log itself refuses a number that does not
follow the last one, and a client that saw number N resumes with the entries after `0-N`.
The log keeps the last 2 000 events and lives an hour after its last write; the database,
not the log, says how a run ended.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Final
from uuid import UUID

from redis.asyncio import Redis
from redis.typing import EncodableT, FieldT

from shosai.features.agent.domain.runs import EVENT_LOG_MAX, EVENT_LOG_TTL
from shosai.features.agent.domain.stream import EventKind, StreamEvent
from shosai.features.agent.infrastructure.run_keys import log_key

KIND: Final = "kind"
DATA: Final = "data"
# Сколько событий читается за раз при возобновлении: журнал короче, чем две такие страницы.
PAGE: Final = 1_000

type Fields = Mapping[bytes | str, bytes | str]


def entry_id(seq: int) -> str:
    """The stream id of event number `seq`."""
    return f"0-{seq}"


def text_of(value: bytes | str) -> str:
    """A reply's bytes as text."""
    return value.decode() if isinstance(value, bytes) else value


def entries_of(reply: object) -> list[tuple[str, Fields]]:
    """`(id, fields)` of every entry in an `XRANGE` or `XREAD` reply, RESP2 or RESP3: the
    protocol is the connection's setting, so the parser does not depend on it (as core's)."""
    if isinstance(reply, dict):
        return [entry for nested in reply.values() for entry in entries_of(nested)]
    if not isinstance(reply, list | tuple):
        return []
    if len(reply) == 2 and isinstance(reply[0], bytes | str) and isinstance(reply[1], dict):
        return [(text_of(reply[0]), reply[1])]
    return [entry for item in reply for entry in entries_of(item)]


def streams_of(reply: object) -> dict[str, list[tuple[str, Fields]]]:
    """The entries of an `XREAD` reply by stream key, RESP2 or RESP3."""
    if isinstance(reply, dict):
        return {text_of(key): entries_of(value) for key, value in reply.items()}
    found: dict[str, list[tuple[str, Fields]]] = {}
    for pair in reply if isinstance(reply, list | tuple) else ():
        if isinstance(pair, list | tuple) and len(pair) == 2 and isinstance(pair[0], bytes | str):
            found[text_of(pair[0])] = entries_of(pair[1])
    return found


def event_of(entry: tuple[str, Fields]) -> StreamEvent:
    """The event a stream entry holds."""
    identifier, fields = entry
    values = {text_of(key): text_of(value) for key, value in fields.items()}
    return StreamEvent(
        int(identifier.split("-", 1)[1]), EventKind(values[KIND]), json.loads(values[DATA])
    )


class RunLog:
    """Appends a run's events and reads them back."""

    def __init__(self, valkey: Redis) -> None:
        self._valkey = valkey

    async def append(self, run_id: UUID, events: Sequence[StreamEvent]) -> None:
        """Add events in their order, in one round trip, and keep the log alive an hour."""
        if not events:
            return
        key = log_key(run_id)
        async with self._valkey.pipeline(transaction=True) as pipeline:
            for event in events:
                fields: dict[FieldT, EncodableT] = {
                    KIND: event.kind.value,
                    DATA: json.dumps(event.data, ensure_ascii=False),
                }
                await pipeline.xadd(
                    key, fields, id=entry_id(event.seq), maxlen=EVENT_LOG_MAX, approximate=True
                )
            await pipeline.expire(key, EVENT_LOG_TTL)
            await pipeline.execute()

    async def after(self, run_id: UUID, seq: int) -> list[StreamEvent]:
        """The events after number `seq`, oldest first."""
        found: list[StreamEvent] = []
        start = f"({entry_id(seq)}"
        while True:
            entries = entries_of(await self._valkey.xrange(log_key(run_id), start, "+", count=PAGE))
            found += [event_of(entry) for entry in entries]
            if len(entries) < PAGE:
                return found
            start = f"({entry_id(found[-1].seq)}"

    async def last(self, run_id: UUID) -> StreamEvent | None:
        """The run's latest event, or None when the log is gone or empty."""
        entries = entries_of(await self._valkey.xrevrange(log_key(run_id), "+", "-", count=1))
        return event_of(entries[0]) if entries else None

    async def kept(self, run_id: UUID) -> bool:
        """Whether the run's log still exists."""
        return bool(await self._valkey.exists(log_key(run_id)))
