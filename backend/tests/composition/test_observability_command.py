"""`shosai observability debug`: the operator switches one account's DEBUG lines on and off."""

import uuid
from pathlib import Path

from redis.asyncio import Redis

from shosai.core.observability.debug_switches import DEBUG_SWITCHES_KEY
from tests.composition.role_process import run_command
from tests.harness.process_environ import slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

USER = uuid.UUID("0190f0f0-0000-7000-8000-0000000000d6")
LISTED = "Включённые отладочные журналы"


async def test_the_cli_switches_debug_on_for_a_user_lists_it_and_switches_it_off(
    run_slot: RunSlot, harness_settings: HarnessSettings, valkey: Redis, tmp_path: Path
) -> None:
    environ = slot_environ(run_slot, harness_settings)
    switch_on = ["observability", "debug", "--user", str(USER), "--minutes", "20",
                 "--reason", "Ticket 42: sign-in fails"]  # fmt: skip

    on, on_lines = await run_command(switch_on, environ, tmp_path / "on.log")
    score = await valkey.zscore(DEBUG_SWITCHES_KEY, f"user:{USER}")
    listed, list_lines = await run_command(["observability", "debug"], environ, tmp_path / "ls.log")
    off, off_lines = await run_command(
        ["observability", "debug", "--user", str(USER), "--off"], environ, tmp_path / "off.log"
    )

    assert (on, listed, off) == (0, 0, 0)
    assert score is not None
    [switched] = [line for line in on_lines if line["message"] == "Отладка включена оператором"]
    assert (switched["user_id"], switched["reason"]) == (str(USER), "Ticket 42: sign-in fails")
    [state] = [line for line in list_lines if line["message"] == LISTED]
    assert [each.split(" ")[0] for each in state["switches"]] == [f"user:{USER}"]
    [ended] = [line for line in off_lines if line["message"] == "Отладка выключена оператором"]
    assert ended["was_on"] is True
    assert await valkey.exists(DEBUG_SWITCHES_KEY) == 0


async def test_switching_on_without_a_reason_is_refused(
    run_slot: RunSlot, harness_settings: HarnessSettings, valkey: Redis, tmp_path: Path
) -> None:
    environ = slot_environ(run_slot, harness_settings)

    code, lines = await run_command(
        ["observability", "debug", "--user", str(USER)], environ, tmp_path / "refused.log"
    )

    assert code == 1
    assert any(line["message"] == "Команда отладки отклонена" for line in lines)
    assert await valkey.exists(DEBUG_SWITCHES_KEY) == 0
