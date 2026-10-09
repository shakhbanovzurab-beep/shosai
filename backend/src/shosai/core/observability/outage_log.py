"""A warning about a failing dependency, written at most once per interval (§16.7).

During an outage of Valkey or the cache every request meets the same failure; a line per
request would flood the log store while saying nothing new. The first failure is logged
at once, later ones at most once per interval with the number held back since the last
line. Every failure is still counted in its metric, so nothing is lost for alerting.
"""

import time
from collections.abc import Callable
from datetime import timedelta
from typing import Final

import structlog

DEFAULT_INTERVAL: Final = timedelta(seconds=10)
log = structlog.stdlib.get_logger(__name__)


class OutageLog:
    """Writes one warning per interval for failures of one dependency operation."""

    def __init__(
        self,
        message: str,
        interval: timedelta = DEFAULT_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._message = message
        self._interval = interval.total_seconds()
        self._clock = clock
        self._next_line_at: float | None = None
        self._held_back = 0

    def failed(self, error: BaseException, **fields: str) -> None:
        """Record one failure; write the warning if the interval has passed since the last."""
        now = self._clock()
        if self._next_line_at is not None and now < self._next_line_at:
            self._held_back += 1
            return
        # Текст ошибки клиента — адрес сервера и причина; пароль в адресе затирает редакция.
        log.warning(
            self._message,
            error_type=type(error).__qualname__,
            failure=str(error)[:200],
            held_back=self._held_back,
            **fields,
        )
        self._held_back = 0
        self._next_line_at = now + self._interval
