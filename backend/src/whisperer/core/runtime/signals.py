"""The stop signal of a process: SIGTERM from the orchestrator, SIGINT from a terminal.

The handler only asks the process to stop; the process then stops taking work, drains
and closes in order (`composition/process.py`). A repeated signal changes nothing: the
container's stop grace period bounds the drain.
"""

import asyncio
import signal
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Final

import structlog

STOP_SIGNALS: Final = (signal.SIGTERM, signal.SIGINT)
log = structlog.stdlib.get_logger(__name__)


@contextmanager
def stop_on_signals(request_stop: Callable[[], None]) -> Iterator[None]:
    """Call `request_stop` on SIGTERM or SIGINT while the block runs on this event loop."""
    loop = asyncio.get_running_loop()
    previous = {stop_signal: signal.getsignal(stop_signal) for stop_signal in STOP_SIGNALS}
    for stop_signal in STOP_SIGNALS:
        loop.add_signal_handler(stop_signal, _received, stop_signal, request_stop)
    try:
        yield
    finally:
        for stop_signal, handler in previous.items():
            loop.remove_signal_handler(stop_signal)
            # Цикл ставит обработчик по умолчанию; возвращается прежний, например SIGINT
            # у asyncio.Runner, который отменяет главную задачу.
            signal.signal(stop_signal, handler)


def _received(stop_signal: signal.Signals, request_stop: Callable[[], None]) -> None:
    log.info("Получен сигнал остановки", signal=stop_signal.name)
    request_stop()
