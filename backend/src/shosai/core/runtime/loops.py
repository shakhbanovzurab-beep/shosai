"""Scheduled loops of the scheduler process: each queues work or refreshes gauges (§4.2, §12).

Loops run only in the scheduler (§14 rule 10): the draft ran them in every API replica,
and they competed with requests and ran N times over. A loop only queues tasks or reads a
gauge; workers do the work. A loop runs at start and then once per interval, never as a
backlog: an iteration that took longer than the interval is followed by the next at once.

A failing iteration is logged with its stack and counted, and the loop goes on: one bad
iteration must not stop delivery for good (draft spec 013). Each success sets
`shosai_loop_last_success_timestamp{loop}`; with `shosai_loop_interval_seconds` it
lets an alert tell a stuck loop from a slow one, whatever its interval.
"""

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import structlog
from prometheus_client import CollectorRegistry, Counter, Gauge

# Итерация цикла только ставит задачи или читает замеры; дольше — значит, зависла.
DEFAULT_DEADLINE: Final = timedelta(seconds=10)
LOOP_NAME: Final = re.compile(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)+")
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ScheduledLoop:
    """A periodic step of the scheduler: its stable name, interval, deadline and work."""

    name: str
    every: timedelta
    run: Callable[[], Awaitable[object]]
    deadline: timedelta = DEFAULT_DEADLINE

    def __post_init__(self) -> None:
        if not LOOP_NAME.fullmatch(self.name):
            message = f"имя цикла {self.name!r} — «срез.цикл» в snake_case"
            raise ValueError(message)
        if self.every <= timedelta(0) or self.deadline <= timedelta(0):
            message = f"у цикла {self.name} интервал и срок итерации положительны"
            raise ValueError(message)


class LoopMetrics:
    """The declared interval, the last success and the failures of every loop."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._interval = Gauge(
            "shosai_loop_interval_seconds",
            "Объявленный интервал цикла планировщика",
            ("loop",),
            registry=registry,
        )
        self._last_success = Gauge(
            "shosai_loop_last_success_timestamp",
            "Unix-время последней успешной итерации цикла планировщика",
            ("loop",),
            registry=registry,
        )
        self._failures = Counter(
            "shosai_loop_failures",
            "Итерации цикла планировщика, завершившиеся ошибкой",
            ("loop",),
            registry=registry,
        )

    def declare(self, loop: ScheduledLoop) -> None:
        """Publish the interval before the first iteration, whatever its outcome."""
        self._interval.labels(loop=loop.name).set(loop.every.total_seconds())

    def succeeded(self, loop: ScheduledLoop) -> None:
        """Record a successful iteration now."""
        self._last_success.labels(loop=loop.name).set(time.time())

    def failed(self, loop: ScheduledLoop) -> None:
        """Count a failed iteration."""
        self._failures.labels(loop=loop.name).inc()


class LoopRunner:
    """Runs every loop in its own task until asked to stop."""

    def __init__(self, loops: Sequence[ScheduledLoop], metrics: LoopMetrics) -> None:
        names = [loop.name for loop in loops]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            message = f"циклы объявлены дважды: {', '.join(duplicates)}"
            raise ValueError(message)
        self._loops = tuple(loops)
        self._metrics = metrics
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> tuple[asyncio.Task[None], ...]:
        """Start every loop; each runs its first iteration at once."""
        self._tasks = [
            asyncio.create_task(self._run(loop), name=f"loop:{loop.name}") for loop in self._loops
        ]
        log.info("Циклы планировщика запущены", loops=[loop.name for loop in self._loops])
        return tuple(self._tasks)

    async def stop(self) -> None:
        """Let each loop finish its iteration in progress, within its deadline, and end."""
        self._stop.set()
        await asyncio.gather(*self._tasks)
        log.info("Циклы планировщика остановлены")

    async def _run(self, loop: ScheduledLoop) -> None:
        self._metrics.declare(loop)
        clock = asyncio.get_running_loop().time
        while not self._stop.is_set():
            started = clock()
            await self._iterate(loop)
            pause = loop.every.total_seconds() - (clock() - started)
            if pause > 0:
                await self._sleep(pause)

    async def _iterate(self, loop: ScheduledLoop) -> None:
        try:
            async with asyncio.timeout(loop.deadline.total_seconds()):
                await loop.run()
        # Итерацию роняет любая ошибка её работы; цикл обязан её пережить (урок черновика).
        except Exception:
            self._metrics.failed(loop)
            log.exception("Итерация цикла завершилась ошибкой", loop=loop.name)
        else:
            self._metrics.succeeded(loop)

    async def _sleep(self, seconds: float) -> None:
        try:
            async with asyncio.timeout(seconds):
                await self._stop.wait()
        except TimeoutError:
            return
