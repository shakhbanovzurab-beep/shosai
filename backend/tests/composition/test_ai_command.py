"""`shosai ai kill-switch`: the operator engages, reads and releases the kill switch (F6-D5)."""

import json
from pathlib import Path

from redis.asyncio import Redis

from shosai.core.ai.spend.kill_switch import KILL_SWITCH_KEY
from tests.composition.role_process import run_command
from tests.harness.process_environ import slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

STATE = "Состояние аварийного выключателя ИИ"


async def test_the_cli_engages_reports_and_releases_the_kill_switch(
    run_slot: RunSlot, harness_settings: HarnessSettings, valkey: Redis, tmp_path: Path
) -> None:
    environ = slot_environ(run_slot, harness_settings)
    engage = ["ai", "kill-switch", "engage", "--reason", "Provider overbilling", "--hours", "1"]

    engaged, engage_lines = await run_command(engage, environ, tmp_path / "engage.log")
    held = await valkey.get(KILL_SWITCH_KEY)
    ttl = await valkey.pttl(KILL_SWITCH_KEY)
    reported, status_lines = await run_command(
        ["ai", "kill-switch", "status"], environ, tmp_path / "status.log"
    )
    released, _ = await run_command(
        ["ai", "kill-switch", "release"], environ, tmp_path / "release.log"
    )

    assert (engaged, reported, released) == (0, 0, 0)
    assert held is not None
    assert json.loads(held) == {"actor": "cli", "reason": "Provider overbilling"}
    assert 0 < ttl <= 3_600_000
    [state] = [line for line in status_lines if line["message"] == STATE]
    assert (state["engaged"], state["actor"]) == (True, "cli")
    assert any(line["message"] == "Аварийный выключатель ИИ включён" for line in engage_lines)
    assert await valkey.get(KILL_SWITCH_KEY) is None


async def test_engaging_without_a_reason_is_refused(
    run_slot: RunSlot, harness_settings: HarnessSettings, valkey: Redis, tmp_path: Path
) -> None:
    environ = slot_environ(run_slot, harness_settings)

    code, lines = await run_command(
        ["ai", "kill-switch", "engage"], environ, tmp_path / "engage.log"
    )

    assert code == 1
    assert any(line["message"] == "Команда выключателя отклонена" for line in lines)
    assert await valkey.get(KILL_SWITCH_KEY) is None
