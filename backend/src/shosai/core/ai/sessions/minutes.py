"""Cost rows of live sessions, one per session and minute, written in batches (F6-C5).

A live session — streaming transcription, translation, voice — consumes for as long as it is
open. Its meter adds up usage by minute of the session's own clock; each minute becomes one
row keyed `<session effect key>:<minute>`. Every interval, and when a session closes, the
batch takes the minutes that ended and writes them together: one transaction per home and
company. A replayed flush finds its keys taken and writes nothing; a crash loses at most the
minutes not yet flushed, which the reconciliation of §16.4 shows.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Final

from shosai.core.ai.calls import EFFECT_KEY_MAX_LENGTH
from shosai.core.ai.recording import CallRecorder, MeteredCall, UsageRecord
from shosai.core.ai.results import Usage

MINUTE: Final = 60.0
# Суффикс минуты — двоеточие и до шести цифр: сессия в 11 дней всё ещё укладывается.
MINUTE_SUFFIX_LENGTH: Final = 7


def merged(total: Usage, more: Usage) -> Usage:
    """Two usages of one minute added up; a reported cost stays only when both report one."""
    reported = None
    if total.reported_cost_usd is not None and more.reported_cost_usd is not None:
        reported = total.reported_cost_usd + more.reported_cost_usd
    return replace(
        total,
        input_tokens=total.input_tokens + more.input_tokens,
        cached_tokens=total.cached_tokens + more.cached_tokens,
        output_tokens=total.output_tokens + more.output_tokens,
        input_audio_tokens=total.input_audio_tokens + more.input_audio_tokens,
        output_audio_tokens=total.output_audio_tokens + more.output_audio_tokens,
        units=total.units + more.units,
        unit=total.unit or more.unit,
        reported_cost_usd=reported,
    )


# Счётчик — изменяемый и сравнивается по тождеству: он хранится в множестве открытых.
@dataclass(slots=True, eq=False)
class SessionMeter:
    """Usage of one open session by minute; the batch takes each minute once it has ended."""

    call: MeteredCall
    started_at: datetime
    started: float
    clock: Callable[[], float]
    minutes: dict[int, Usage] = field(default_factory=dict)
    closed: bool = False

    def add(self, usage: Usage) -> None:
        """Count usage in the minute now running."""
        minute = int((self.clock() - self.started) // MINUTE)
        current = self.minutes.get(minute)
        self.minutes[minute] = usage if current is None else merged(current, usage)

    def ended(self, *, everything: bool) -> list[UsageRecord]:
        """The minutes that ended, removed from the meter; all of them once it is closed."""
        running = int((self.clock() - self.started) // MINUTE)
        done = sorted(m for m in self.minutes if everything or m < running)
        key = self.call.context.effect_key
        return [
            UsageRecord(
                call=self.call,
                effect_key=f"{key}:{minute}",
                created_at=self.started_at + timedelta(minutes=minute),
                usage=self.minutes.pop(minute),
            )
            for minute in done
        ]


class MinuteRows:
    """The process's open meters and the batch that writes their ended minutes."""

    def __init__(
        self,
        recorder: CallRecorder,
        interval: float = MINUTE,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._recorder = recorder
        self._interval = interval
        self._clock = clock
        self._meters: set[SessionMeter] = set()

    def open(self, call: MeteredCall) -> SessionMeter:
        """A meter for a session that starts now."""
        if len(call.context.effect_key) > EFFECT_KEY_MAX_LENGTH - MINUTE_SUFFIX_LENGTH:
            message = "ключ эффекта сессии оставляет место для номера минуты"
            raise ValueError(message)
        meter = SessionMeter(call, datetime.now(UTC), self._clock(), self._clock)
        self._meters.add(meter)
        return meter

    async def close(self, meter: SessionMeter) -> None:
        """Stop the meter and write all its minutes, the running one included."""
        meter.closed = True
        await self.flush()

    async def flush(self) -> None:
        """Write the minutes that ended; the writer defers or logs what its homes refuse."""
        records = []
        for meter in list(self._meters):
            records += meter.ended(everything=meter.closed)
            if meter.closed:
                self._meters.discard(meter)
        await self._recorder.record_many(records)

    @asynccontextmanager
    async def running(self) -> AsyncIterator[None]:
        """Flush every interval while the process runs, and once more at stop."""
        task = asyncio.create_task(self._every_interval(), name="ai.minute_rows")
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            for meter in self._meters:
                meter.closed = True
            await self.flush()

    async def _every_interval(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self.flush()
