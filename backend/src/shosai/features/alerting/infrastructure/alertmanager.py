"""Alertmanager's v2 API: one alert per business event (F5-D5).

The alert carries the event's id as a label, so a redelivered event is the same alert to
Alertmanager, which notifies once. It ends after `ALERT_LIFETIME`: longer than the batching
of notices (5 min) and the wait of tickets, so it is sent before it ends, and short, so it
is never repeated. A failed connection, a timeout or a 5xx earn another delivery of the
task; a 4xx is a defect of the alert and is not retried.
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

import httpx
import structlog
from pydantic import HttpUrl

from shosai.features.alerting.infrastructure.metrics import AlertingMetrics

ALERTS_PATH: Final = "/api/v2/alerts"
ALERT_LIFETIME: Final = timedelta(minutes=30)
TIMEOUT: Final = httpx.Timeout(5.0, connect=2.0)
log = structlog.stdlib.get_logger(__name__)


class AlertmanagerUnavailableError(Exception):
    """Alertmanager did not take the alert: unreachable, too slow or failing; worth a retry."""


class AlertRejectedError(Exception):
    """Alertmanager refused the alert as invalid; another delivery would be refused too."""


@dataclass(frozen=True, slots=True)
class PostedAlert:
    """An alert as Alertmanager's API takes it."""

    labels: Mapping[str, str]
    annotations: Mapping[str, str]
    starts_at: datetime
    ends_at: datetime

    def body(self) -> list[dict[str, object]]:
        """The request body: a list of one alert."""
        return [
            {
                "labels": dict(self.labels),
                "annotations": dict(self.annotations),
                "startsAt": self.starts_at.isoformat(),
                "endsAt": self.ends_at.isoformat(),
            }
        ]


class Alertmanager:
    """Posts alerts over one HTTP client of the process."""

    def __init__(self, client: httpx.AsyncClient, metrics: AlertingMetrics) -> None:
        self._client = client
        self._metrics = metrics

    async def post(self, alert: PostedAlert) -> None:
        """Hand the alert over; raise when Alertmanager did not take it."""
        kind = alert.labels["kind"]
        try:
            response = await self._client.post(ALERTS_PATH, json=alert.body())
        except httpx.TransportError as error:
            self._metrics.posted(kind, "unavailable")
            log.warning("Alertmanager недоступен, оповещение будет повторено", kind=kind,
                        error=type(error).__name__)  # fmt: skip
            raise AlertmanagerUnavailableError(type(error).__name__) from None
        if response.is_server_error:
            self._metrics.posted(kind, "unavailable")
            log.warning("Alertmanager ответил ошибкой, оповещение будет повторено", kind=kind,
                        status=response.status_code)  # fmt: skip
            raise AlertmanagerUnavailableError(f"HTTP {response.status_code}")
        if response.is_error:
            self._metrics.posted(kind, "rejected")
            log.error("Alertmanager отклонил оповещение", kind=kind, status=response.status_code)
            raise AlertRejectedError(f"HTTP {response.status_code}")
        self._metrics.posted(kind, "accepted")
        log.info("Оповещение передано в Alertmanager", kind=kind)


@asynccontextmanager
async def open_alertmanager(url: HttpUrl, metrics: AlertingMetrics) -> AsyncIterator[Alertmanager]:
    """Alertmanager's client for the life of the process."""
    async with httpx.AsyncClient(base_url=str(url), timeout=TIMEOUT) as client:
        yield Alertmanager(client, metrics)
