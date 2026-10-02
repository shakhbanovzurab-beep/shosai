"""Shared fixtures of the backend tests.

The test database slot is claimed by the first test that needs it and held until the
run ends (ADR 0009): both homes are migrated to the head after the claim and downgraded
to the base at the end, before the catalog check. The slot also names the run's Valkey
and cache databases and its prefix in the bucket (`tests/harness/shared_services.py`).
Tests without databases and services run without the local environment too.
A harness failure is reported as short text without a traceback: its local variables
would contain the whole process environment.
"""

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from tests.harness.guards import UnsafeTestTargetError, ensure_safe_targets
from tests.harness.migrations import migrate_slot, unmigrate_slot
from tests.harness.run_slot import RunSlot, open_run_slot
from tests.harness.settings import HarnessConfigurationError, HarnessSettings
from tests.harness.slots import NoFreeSlotError

RUN_SLOT_SUMMARY = pytest.StashKey[list[str]]()
pytest_plugins = (
    "tests.harness.database_access",
    "tests.harness.shared_services",
    "tests.core.db.probe_table",
)


@pytest.fixture(scope="session")
def harness_settings() -> HarnessSettings:
    """Settings from the TEST_* variables that passed the safety checks."""
    try:
        settings = HarnessSettings.from_environ(os.environ)
        ensure_safe_targets(settings, os.environ)
    except (HarnessConfigurationError, UnsafeTestTargetError) as error:
        raise harness_stopped(error) from None
    return settings


@pytest_asyncio.fixture(scope="session")
async def run_slot(
    pytestconfig: pytest.Config, harness_settings: HarnessSettings
) -> AsyncIterator[RunSlot]:
    """The run's slot in both homes; at the end each home's catalog must match its reference."""
    numbers = range(1, harness_settings.database_slots + 1)
    try:
        slot = await open_run_slot(harness_settings, numbers)
    except (HarnessConfigurationError, UnsafeTestTargetError, NoFreeSlotError) as error:
        raise harness_stopped(error) from None
    pytestconfig.stash[RUN_SLOT_SUMMARY] = slot.summary()
    try:
        await migrate_slot(slot.claimed)
        yield slot
        await unmigrate_slot(slot.claimed)
        changes = await slot.catalog_changes()
        if changes:
            pytest.fail(
                "Схема тестовых баз изменилась за прогон:\n" + "\n".join(changes), pytrace=False
            )
    finally:
        await slot.claimed.release()


def harness_stopped(error: Exception) -> BaseException:
    """A short test failure without a traceback or an exception chain."""
    return pytest.fail.Exception(f"Харнесс тестовых баз остановлен:\n{error}", pytrace=False)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    """Print the claimed slot and what the claim restored, if the run used the databases."""
    for line in config.stash.get(RUN_SLOT_SUMMARY, []):
        terminalreporter.write_line(line)
