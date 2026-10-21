"""`shosai ai kill-switch`: the operator engages, reads and releases the kill switch (F6-D5)."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from redis.asyncio import Redis

from shosai.core.ai.costs.entries import CostEntry
from shosai.core.ai.spend.kill_switch import KILL_SWITCH_KEY
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id
from tests.composition.role_process import run_command
from tests.core.ai.bench import ORG_ID, USER_ID, ai_bench
from tests.doubles.business_calendar import MOSCOW
from tests.harness.database_access import DatabaseAccess
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


async def test_the_cli_rebuilds_the_spend_counters_from_the_cost_rows(
    run_slot: RunSlot,
    harness_settings: HarnessSettings,
    homes: DatabaseAccess,
    valkey: Redis,
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC)
    entry = CostEntry(
        home=Home.EU, user_id=USER_ID, org_id=ORG_ID, cost_id=new_id(), created_at=now,
        effect_key="cli:rebuild", provider="openrouter", model="probe/chat", kind="chat",
        feature="probe.chat", call_class="standard", origin="interactive", outcome="ok",
        cost_usd=Decimal("0.42"), cost_source="reported",
    )  # fmt: skip
    await ai_bench(homes.transactions).writer.write(entry)

    code, lines = await run_command(
        ["ai", "rebuild-spend-counters"], slot_environ(run_slot, harness_settings),
        tmp_path / "rebuild.log",
    )  # fmt: skip

    assert code == 0
    assert any(line["message"].startswith("Счётчики расходов пересобраны") for line in lines)
    # Сутки счётчика — деловые (Москва, ADR 0058), как их считает команда по настройке по умолчанию.
    day = MOSCOW.date_of(now)
    assert await valkey.get(f"shosai:ai:spend:global:day:{day:%Y%m%d}") == b"420000"
