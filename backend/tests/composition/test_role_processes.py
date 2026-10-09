"""Each role starts as its own process against the local homes, answers, and drains on SIGTERM.

The processes run over the run's slot (`tests/harness/process_environ.py`): they write
tick markers and consumer groups into the slot's Valkey database, which the `valkey`
fixture empties after each test.
"""

import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from redis.asyncio import Redis

from shosai.core.kernel.homes import Home
from tests.composition.role_process import RoleProcess, messages, role_process
from tests.core.db.tcp_proxy import CountingProxy, Upstream, through
from tests.harness.process_environ import slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

ROLES = {
    "api": ("api",),
    "ws": ("ws",),
    "workers": ("workers", "--queue", "default"),
    "scheduler": ("scheduler",),
}
PUBLIC_ROLES = frozenset({"api", "ws"})
CORE_DEPENDENCIES = ("homes.ru", "homes.eu", "valkey", "cache", "storage")
FAILURE_LEVELS = frozenset({"error", "critical"})
WAIT_SECONDS = 15.0


async def readiness_until(
    running: RoleProcess, holds: Callable[[dict[str, Any]], bool]
) -> dict[str, Any]:
    """The first readiness body for which `holds` is true, within the bound."""
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        body: dict[str, Any] = (await running.get("OPS_PORT", "/readyz")).json()
        if holds(body):
            return body
        await asyncio.sleep(0.2)
    pytest.fail(f"готовность не пришла в ожидаемое состояние:\n{running.tail()}")


@pytest.mark.parametrize("role", ROLES)
async def test_each_role_starts_answers_its_probes_and_drains_on_sigterm(
    role: str,
    run_slot: RunSlot,
    harness_settings: HarnessSettings,
    valkey: Redis,
    tmp_path: Path,
) -> None:
    environ = slot_environ(run_slot, harness_settings)
    async with role_process(ROLES[role], environ, tmp_path / "role.log") as running:
        readiness = await running.wait_ready()
        live = await running.get("OPS_PORT", "/livez")
        health = await running.get("HTTP_PORT", "/v1/health") if role in PUBLIC_ROLES else None
        metrics = await running.get("OPS_PORT", "/metrics")
        code = await running.stop()

    lines = running.lines()
    assert readiness == {"status": "ready", "dependencies": dict.fromkeys(CORE_DEPENDENCIES, "ok")}
    assert live.json() == {"status": "ok"}
    if health is not None:
        assert (health.status_code, health.json()) == (200, {"status": "ok"})
    assert "shosai_event_loop_lag_seconds_bucket" in metrics.text
    assert code == 0
    assert {line["role"] for line in lines} == {role}
    assert [line for line in lines if line["level"] in FAILURE_LEVELS] == []
    assert "Получен сигнал остановки" in messages(lines)
    assert (lines[-1]["message"], lines[-1]["exit_code"]) == ("Процесс остановлен", 0)


async def test_a_russian_home_out_of_reach_leaves_the_process_ready_and_is_reported(
    run_slot: RunSlot, harness_settings: HarnessSettings, valkey: Redis, tmp_path: Path
) -> None:
    proxy = CountingProxy(None)
    port = await proxy.start()
    russian = run_slot.claimed.targets(Home.RU).application
    environ = slot_environ(
        run_slot,
        harness_settings,
        HOME_RU_DATABASE_URL=through(russian.url(), port).get_secret_value(),
    )
    try:
        async with role_process(("api",), environ, tmp_path / "api.log") as running:
            unreachable_at_start = await running.wait_ready()
            proxy.upstream = Upstream(russian.host, russian.port)
            back = await readiness_until(running, lambda body: is_up(body, "homes.ru"))
            await proxy.cut()
            gone = await running.get("OPS_PORT", "/readyz")
            code = await running.stop()
    finally:
        await proxy.stop()

    assert unreachable_at_start["dependencies"] == {
        **dict.fromkeys(CORE_DEPENDENCIES, "ok"),
        "homes.ru": "down",
    }
    assert back["status"] == "ready"
    assert gone.status_code == 200
    assert gone.json()["dependencies"]["homes.ru"] == "down"
    assert gone.json()["dependencies"]["homes.eu"] == "ok"
    assert "База дома не проверена: недоступна" in messages(running.lines())
    assert code == 0


def is_up(body: dict[str, Any], dependency: str) -> bool:
    """Whether the readiness body reports the dependency `ok`."""
    return bool(body["dependencies"].get(dependency) == "ok")
