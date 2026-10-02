"""A process that cannot start exits 1 with one critical line naming the failed step.

Settings and the ops port fail before any database is touched, so those tests need no
slot; the database step runs against the slot with the homes' addresses swapped.
"""

import socket
from pathlib import Path
from typing import Any

from tests.composition.role_process import run_command
from tests.core.config.sample_environ import SAMPLE_SECRET, local_environ, production_environ
from tests.harness.process_environ import LOOPBACK, slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

EXIT_FAILED = 1


def critical(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The critical lines of a log."""
    return [line for line in lines if line["level"] == "critical"]


async def test_rejected_settings_are_named_in_one_line_without_values(tmp_path: Path) -> None:
    environ = local_environ(VALKEY_URL=f"http://:{SAMPLE_SECRET}@valkey:6379/0")
    del environ["ENVIRONMENT"]

    code, lines = await run_command(("api",), environ, tmp_path / "api.log")

    assert code == EXIT_FAILED
    [line] = lines
    assert (line["level"], line["step"], line["role"]) == ("critical", "settings", "api")
    assert "ENVIRONMENT: обязательная переменная не задана" in line["reason"]
    assert "VALKEY_URL" in line["reason"]
    assert SAMPLE_SECRET not in str(lines)


async def test_the_production_gate_stops_the_start(tmp_path: Path) -> None:
    environ = production_environ(API_DOCS_ENABLED="true")

    code, lines = await run_command(("scheduler",), environ, tmp_path / "scheduler.log")

    assert code == EXIT_FAILED
    [line] = critical(lines)
    assert line["step"] == "settings"
    assert "API_DOCS_ENABLED" in line["reason"]


async def test_a_taken_ops_port_stops_the_start(tmp_path: Path) -> None:
    with socket.create_server((LOOPBACK, 0)) as taken:
        port = taken.getsockname()[1]
        environ = local_environ(OPS_PORT=str(port), HTTP_PORT=str(port + 1))
        code, lines = await run_command(("api",), environ, tmp_path / "api.log")

    assert code == EXIT_FAILED
    [line] = critical(lines)
    assert line["step"] == "ops"
    assert "Address already in use" in line["exception"]


async def test_swapped_home_addresses_stop_the_start_at_the_database_step(
    run_slot: RunSlot, harness_settings: HarnessSettings, tmp_path: Path
) -> None:
    environ = slot_environ(run_slot, harness_settings)
    environ["HOME_RU_DATABASE_URL"], environ["HOME_EU_DATABASE_URL"] = (
        environ["HOME_EU_DATABASE_URL"],
        environ["HOME_RU_DATABASE_URL"],
    )

    code, lines = await run_command(("workers", "--queue", "bulk"), environ, tmp_path / "w.log")

    assert code == EXIT_FAILED
    failure = next(line for line in critical(lines) if line.get("step"))
    assert failure["step"] == "databases"
    assert "HOME_RU_DATABASE_URL: ведёт в базу дома eu" in failure["exception"]
    assert "Процесс готов к работе" not in str(lines)
