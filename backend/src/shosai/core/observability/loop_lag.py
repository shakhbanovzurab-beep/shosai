"""Event-loop lag: how late the loop wakes a coroutine that asked to sleep (§16.5).

A blocking call in a coroutine delays everything else on the loop; the lag shows it per
process before requests start to time out.
"""

import asyncio

from prometheus_client import Histogram

LOOP_LAG_INTERVAL_SECONDS = 0.5


async def watch_event_loop_lag(
    histogram: Histogram, interval: float = LOOP_LAG_INTERVAL_SECONDS
) -> None:
    """Observe the lag of every wake-up into the histogram until the task is cancelled."""
    loop = asyncio.get_running_loop()
    while True:
        planned = loop.time() + interval
        await asyncio.sleep(interval)
        histogram.observe(max(loop.time() - planned, 0.0))
