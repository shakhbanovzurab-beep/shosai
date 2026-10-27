"""Whether Jev's endpoint keeps nothing, as last checked (ADR 0069 DL-D1, plan §1.4).

Jev reads a person's text under Leo's consent only while every endpoint of the pinned model
is on OpenRouter's zero-data-retention list. A daily task reads the list and keeps the
answer in Valkey for three days; each deciding process reads it at most once a minute.
Anything but a fresh "yes" — an endpoint off the list, a status older than three days, a
Valkey that does not answer — is "no", and every point runs its rule (`not_zdr`).
"""

import time
from collections.abc import Callable
from datetime import timedelta
from typing import Final

import structlog
from prometheus_client import CollectorRegistry, Gauge
from redis.asyncio import Redis

from shosai.core.kv.connection import REDIS_FAILURES
from shosai.core.kv.keys import build_key

KEPT_FOR: Final = timedelta(days=3)
FRESH_FOR: Final = timedelta(seconds=60)
YES: Final = b"1"
log = structlog.stdlib.get_logger(__name__)


def status_key(model: str) -> str:
    """The Valkey key of a model's zero-retention status."""
    return build_key("decisions", "zero_retention", model.replace("/", "."))


class ProviderTerms:
    """The pinned Jev model's zero-retention status, kept three days, read once a minute."""

    def __init__(
        self,
        valkey: Redis,
        model: str,
        registry: CollectorRegistry,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._valkey = valkey
        self._key = status_key(model)
        self._clock = clock
        self._known: tuple[float, bool] | None = None
        self._gauge = Gauge(
            "shosai_decision_zero_retention",
            "1 — все эндпоинты закреплённой модели Jev в списке нулевого хранения OpenRouter",
            registry=registry,
        )

    async def zero_retention(self) -> bool:
        """Whether Jev may read text now."""
        now = self._clock()
        if self._known is not None and now - self._known[0] < FRESH_FOR.total_seconds():
            return self._known[1]
        try:
            kept = await self._valkey.get(self._key) == YES
        except REDIS_FAILURES:
            kept = False
            log.warning("Статус нулевого хранения Jev не прочитан: решают правила")
        self._known = (now, kept)
        self._gauge.set(1 if kept else 0)
        return kept

    async def record(self, *, keeps_nothing: bool) -> None:
        """Keep the day's answer for three days."""
        value = YES if keeps_nothing else b"0"
        await self._valkey.set(self._key, value, ex=int(KEPT_FOR.total_seconds()))
        self._known = None
