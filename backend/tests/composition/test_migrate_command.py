"""`whisperer migrate` applies and reads the one history in both homes, RU first (ADR 0010).

The run's slot is already at the head, so `upgrade` must change nothing and succeed.
"""

from pathlib import Path

from tests.composition.role_process import run_command
from tests.harness.process_environ import slot_environ
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings
from whisperer.core.db.migrations import MigrationHistory

REVISION_LINE = "Ревизия базы дома"


async def test_upgrade_at_the_head_logs_both_homes_in_order(
    run_slot: RunSlot, harness_settings: HarnessSettings, tmp_path: Path
) -> None:
    environ = slot_environ(run_slot, harness_settings)

    code, lines = await run_command(("migrate", "upgrade"), environ, tmp_path / "migrate.log")

    revisions = [
        (line["home"], line["revision"]) for line in lines if line["message"] == REVISION_LINE
    ]
    head = MigrationHistory.load().head
    assert code == 0
    assert revisions == [("ru", head), ("eu", head)]
    assert {line["role"] for line in lines} == {"migrate"}


async def test_current_reads_without_changing_anything(
    run_slot: RunSlot, harness_settings: HarnessSettings, tmp_path: Path
) -> None:
    environ = slot_environ(run_slot, harness_settings)

    code, lines = await run_command(("migrate", "current"), environ, tmp_path / "migrate.log")

    assert code == 0
    assert [line["home"] for line in lines if line["message"] == REVISION_LINE] == ["ru", "eu"]
    assert "Миграция домов начата" not in str(lines)


async def test_without_migration_addresses_nothing_starts(
    run_slot: RunSlot, harness_settings: HarnessSettings, tmp_path: Path
) -> None:
    environ = slot_environ(run_slot, harness_settings)
    del environ["HOME_RU_MIGRATION_DATABASE_URL"], environ["HOME_EU_MIGRATION_DATABASE_URL"]

    code, lines = await run_command(("migrate", "upgrade"), environ, tmp_path / "migrate.log")

    assert code == 1
    [line] = [line for line in lines if line["level"] == "critical"]
    assert line["message"] == "Миграция не начата"
    assert "HOME_RU_MIGRATION_DATABASE_URL" in line["reason"]
    assert "HOME_EU_MIGRATION_DATABASE_URL" in line["reason"]
