"""Handing an alert to Alertmanager: what earns a retry and what is a defect."""

import json
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime

import httpx
import pytest
from prometheus_client import CollectorRegistry

from shosai.core.config.values import Environment
from shosai.core.kernel.homes import Home
from shosai.features.alerting.channels.tasks import AlertPayload, posted_alert
from shosai.features.alerting.domain.alerts import spend_exceeded
from shosai.features.alerting.infrastructure.alertmanager import (
    ALERT_LIFETIME,
    Alertmanager,
    AlertmanagerUnavailableError,
    AlertRejectedError,
)
from shosai.features.alerting.infrastructure.metrics import AlertingMetrics

USER_ID = uuid.UUID("0190f0f0-0000-7000-8000-0000000000a1")
EVENT_ID = uuid.UUID("0190f0f0-0000-7000-8000-0000000000e1")
OCCURRED = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 16, 12, 3, tzinfo=UTC)
KIND = "ai.user_spend.exceeded"


def payload() -> AlertPayload:
    """A spend ticket of a person in the Russian home."""
    alert = spend_exceeded(
        "https://shosai.tech", USER_ID, date(2026, 10, 16), 25_000_000, 20_000_000
    )
    return AlertPayload(
        home=Home.RU, user_id=USER_ID, event_id=EVENT_ID, occurred_at=OCCURRED, alert=alert
    )


def alertmanager(
    handle: Callable[[httpx.Request], httpx.Response], registry: CollectorRegistry
) -> Alertmanager:
    """A client over a transport that answers with `handle`."""
    client = httpx.AsyncClient(
        base_url="http://alertmanager:9093", transport=httpx.MockTransport(handle)
    )
    return Alertmanager(client, AlertingMetrics(registry))


def posts(registry: CollectorRegistry, outcome: str) -> float:
    """Attempts of the spend kind that ended with `outcome`."""
    labels = {"kind": KIND, "outcome": outcome}
    return registry.get_sample_value("shosai_alerting_posts_total", labels) or 0.0


async def test_the_alert_names_its_event_so_a_repeat_is_the_same_alert() -> None:
    requests: list[httpx.Request] = []
    registry = CollectorRegistry()

    def accept(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    await alertmanager(accept, registry).post(posted_alert(payload(), Environment.STAGING, NOW))

    [request] = requests
    assert (request.method, request.url.path) == ("POST", "/api/v2/alerts")
    [body] = json.loads(request.content)
    assert body["labels"] == {
        "alertname": "UserSpendExceeded",
        "severity": "ticket",
        "kind": KIND,
        "event_id": str(EVENT_ID),
        "home": "ru",
        "environment": "staging",
    }
    assert body["annotations"]["admin_card"] == f"https://shosai.tech/admin/users/{USER_ID}"
    assert body["annotations"]["runbook"] == "docs/runbooks/alerts.md#user-spend-exceeded"
    assert datetime.fromisoformat(body["startsAt"]) == OCCURRED
    assert datetime.fromisoformat(body["endsAt"]) == NOW + ALERT_LIFETIME
    assert posts(registry, "accepted") == 1


def test_development_is_named_local_as_in_prometheus() -> None:
    alert = posted_alert(payload(), Environment.DEVELOPMENT, NOW)

    assert alert.labels["environment"] == "local"


@pytest.mark.parametrize(
    "handle",
    [
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("refused", request=request)),
        lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=request)),
        lambda _request: httpx.Response(503),
    ],
    ids=["refused", "timeout", "server-error"],
)
async def test_an_unreachable_or_failing_alertmanager_earns_a_retry(
    handle: Callable[[httpx.Request], httpx.Response],
) -> None:
    registry = CollectorRegistry()

    with pytest.raises(AlertmanagerUnavailableError):
        await alertmanager(handle, registry).post(posted_alert(payload(), Environment.STAGING, NOW))

    assert posts(registry, "unavailable") == 1


async def test_a_refused_alert_is_a_defect_and_is_not_retried() -> None:
    registry = CollectorRegistry()

    with pytest.raises(AlertRejectedError):
        await alertmanager(lambda _request: httpx.Response(400), registry).post(
            posted_alert(payload(), Environment.STAGING, NOW)
        )

    assert posts(registry, "rejected") == 1
