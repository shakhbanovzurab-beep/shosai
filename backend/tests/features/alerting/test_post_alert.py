"""The delivery task: Alertmanager down → retries, then the dead letter that pages (§16.4)."""

import json
import uuid
from datetime import UTC, date, datetime

import httpx
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.config.values import Environment
from shosai.core.kernel.homes import Home
from shosai.core.tasks.declaration import MAX_DELIVERIES
from shosai.features.alerting.channels.tasks import POST_ALERT, AlertPayload, task_handlers
from shosai.features.alerting.domain.alerts import spend_exceeded
from shosai.features.alerting.infrastructure.alertmanager import Alertmanager
from shosai.features.alerting.infrastructure.metrics import AlertingMetrics
from tests.core.tasks.workbench import eventually, running, settled, workbench

USER_ID = uuid.UUID("0190f0f0-0000-7000-8000-0000000000a3")
EVENT_ID = uuid.UUID("0190f0f0-0000-7000-8000-0000000000e3")


def payload() -> AlertPayload:
    """A spend ticket of a person in the EU home."""
    alert = spend_exceeded(
        "https://shosai.tech", USER_ID, date(2026, 10, 16), 21_000_000, 20_000_000
    )
    return AlertPayload(
        home=Home.EU, user_id=USER_ID, event_id=EVENT_ID,
        occurred_at=datetime(2026, 10, 16, 9, 0, tzinfo=UTC), alert=alert,
    )  # fmt: skip


def refusing(request: httpx.Request) -> httpx.Response:
    """Alertmanager is down: the connection is refused."""
    raise httpx.ConnectError("connection refused", request=request)


async def test_an_alertmanager_that_stays_down_gets_every_delivery_then_the_dead_letter(
    valkey: Redis,
) -> None:
    client = httpx.AsyncClient(
        base_url="http://alertmanager:9093", transport=httpx.MockTransport(refusing)
    )
    manager = Alertmanager(client, AlertingMetrics(CollectorRegistry()))
    bench = workbench(valkey, task_handlers(manager, Environment.STAGING))

    async with running(bench.broker()):
        await bench.system.sender.send(POST_ALERT, payload())
        await eventually(settled(bench, POST_ALERT.name, "dead_lettered"))

    assert (
        bench.sample(
            "shosai_task_runs_total", queue="default", task=POST_ALERT.name, outcome="retried"
        )
        == MAX_DELIVERIES - 1
    )
    [entry] = await bench.dead_letters()
    assert entry["task"] == POST_ALERT.name
    assert entry["error_type"].endswith("AlertmanagerUnavailableError")
    assert "@" not in json.dumps(entry)


async def test_a_delivery_after_alertmanager_is_back_hands_the_alert_over(valkey: Redis) -> None:
    attempts: list[int] = []

    def back_on_the_second_try(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200)

    transport = httpx.MockTransport(back_on_the_second_try)
    client = httpx.AsyncClient(base_url="http://alertmanager:9093", transport=transport)
    manager = Alertmanager(client, AlertingMetrics(CollectorRegistry()))
    bench = workbench(valkey, task_handlers(manager, Environment.STAGING))

    async with running(bench.broker()):
        await bench.system.sender.send(POST_ALERT, payload())
        await eventually(settled(bench, POST_ALERT.name, "succeeded"))

    assert len(attempts) == 2
    assert await bench.dead_letters() == []
