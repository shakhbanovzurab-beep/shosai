"""One retry before the first byte, within a per-process budget (F6-C15, §4.3).

A failure before any byte of an answer — a refused connection, or 429, 502, 503, 504 —
leaves the request unanswered, so it is sent once more after a short random pause. During
an outage every process would double the provider's load, so retries per provider are
bounded: at most 20% of the calls of the last 10 seconds, plus 3, so a quiet process can
still ride out a single blip. The budget lives in the process and needs no shared state.
"""

import asyncio
import secrets
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Final

from shosai.core.ai.calls import Provider
from shosai.core.ai.errors import AiCallError
from shosai.core.ai.resilience.metrics import ResilienceMetrics

WINDOW: Final = 10.0
SHARE: Final = 0.2
FLOOR: Final = 3
PAUSE: Final = (0.05, 0.25)
_jitter = secrets.SystemRandom()


class RetryBudget:
    """Retries per provider in a sliding window, bounded by the calls in it."""

    def __init__(
        self, metrics: ResilienceMetrics, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._metrics = metrics
        self._clock = clock
        self._calls: dict[Provider, deque[float]] = {}
        self._retries: dict[Provider, deque[float]] = {}

    async def attempt[R](self, provider: Provider, send: Callable[[], Awaitable[R]]) -> R:
        """Send, and once more if the first failed before any byte and the budget allows."""
        self._note(self._calls, provider)
        try:
            return await send()
        except AiCallError as failure:
            if not failure.retryable or not self.spend(provider):
                raise
        await asyncio.sleep(_jitter.uniform(*PAUSE))
        return await send()

    def spend(self, provider: Provider) -> bool:
        """Take one retry from the budget, or say it is spent."""
        calls, retries = self._recent(self._calls, provider), self._recent(self._retries, provider)
        if retries >= FLOOR + SHARE * calls:
            self._metrics.retry(provider.value, "budget_spent")
            return False
        self._note(self._retries, provider)
        self._metrics.retry(provider.value, "retried")
        return True

    def _note(self, moments: dict[Provider, deque[float]], provider: Provider) -> None:
        moments.setdefault(provider, deque()).append(self._clock())

    def _recent(self, moments: dict[Provider, deque[float]], provider: Provider) -> int:
        window = moments.setdefault(provider, deque())
        since = self._clock() - WINDOW
        while window and window[0] < since:
            window.popleft()
        return len(window)
