"""SIGTERM and SIGINT ask the process to stop; the handlers live only inside the block."""

import asyncio
import os
import signal

import pytest

from whisperer.core.runtime.signals import stop_on_signals


@pytest.mark.parametrize("stop_signal", [signal.SIGTERM, signal.SIGINT])
async def test_a_stop_signal_asks_the_process_to_stop(stop_signal: signal.Signals) -> None:
    requested = asyncio.Event()

    with stop_on_signals(requested.set):
        os.kill(os.getpid(), stop_signal)
        await asyncio.wait_for(requested.wait(), timeout=5)

    assert requested.is_set()


async def test_the_handlers_are_removed_after_the_block() -> None:
    before = {stop: signal.getsignal(stop) for stop in (signal.SIGTERM, signal.SIGINT)}

    with stop_on_signals(lambda: None):
        pass

    assert {stop: signal.getsignal(stop) for stop in before} == before
