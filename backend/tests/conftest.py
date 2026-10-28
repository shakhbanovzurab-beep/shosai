"""Shared fixtures of the backend tests.

The test database slot is claimed by the first test that needs it and held until the
run ends (ADR 0009): both homes are migrated to the head after the claim and downgraded
to the base at the end, before the catalog check. The slot also names the run's Valkey
and cache databases and its prefix in the bucket (`tests/harness/shared_services.py`).
Tests without databases and services run without the local environment too.
A harness failure is reported as short text without a traceback: its local variables
would contain the whole process environment.
"""

import logging
import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
import structlog

from tests.harness.guards import UnsafeTestTargetError, ensure_safe_targets
from tests.harness.migrations import migrate_slot, unmigrate_slot
from tests.harness.run_slot import RunSlot, open_run_slot
from tests.harness.settings import HarnessConfigurationError, HarnessSettings
from tests.harness.slots import NoFreeSlotError

RUN_SLOT_SUMMARY = pytest.StashKey[list[str]]()
UVICORN_ACCESS_LOGGER = "uvicorn.access"
pytest_plugins = (
    "tests.harness.database_access",
    "tests.harness.shared_services",
    "tests.core.db.probe_table",
    "tests.features.workspaces.probe_resources",
    "tests.features.billing.catalogue_bench",
    "tests.features.billing.entitlement_bench",
    "tests.features.billing.people_bench",
    "tests.features.files.upload_bench",
    "tests.features.files.file_bench",
    "tests.features.notes.meeting_bench",
    "tests.features.notes.notes_bench",
    "tests.features.notes.library_bench",
    "tests.features.notes.deletion_bench",
    "tests.features.notes.recording_bench",
    "tests.features.notes.native_bench",
    "tests.features.notes.share_bench",
    "tests.features.notes.write_bench",
    "tests.features.tasks.task_bench",
    "tests.features.agent.thread_bench",
    "tests.features.agent.bench_doubles",
    "tests.features.agent.turn_bench",
    "tests.features.agent.feedback_bench",
    "tests.features.agent.action_bench",
    "tests.features.agent.proxy_bench",
    "tests.features.agent.skills_bench",
    "tests.features.capture.voice_bench",
    "tests.features.memory.facts_api_bench",
    "tests.features.memory.recall_bench",
    "tests.features.memory.admission_bench",
    "tests.features.memory.tools_bench",
    "tests.features.memory.summary_bench",
    "tests.features.memory.recollection_bench",
    "tests.features.memory.upkeep_bench",
    "tests.features.meetings.room_bench",
    "tests.features.meetings.broadcast_bench",
    "tests.features.studio.person_bench",
)


def pytest_configure(config: pytest.Config) -> None:
    """Lines of a test without its own logging pipeline: INFO and up, plain tracebacks.

    structlog's defaults write DEBUG too, with colored tracebacks that take tens of
    milliseconds to render on the event loop; a test with a 50 ms deadline then fails on
    the rendering of another task's lines. Processes always configure their pipeline, at
    INFO unless `LOG_LEVEL` says otherwise.
    """
    del config
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=True),
            structlog.dev.ConsoleRenderer(
                colors=False, exception_formatter=structlog.dev.plain_traceback
            ),
        ],
        cache_logger_on_first_use=False,
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """`--update-openapi` and `--update-rules` rewrite the files generated from the code."""
    parser.addoption(
        "--update-openapi",
        action="store_true",
        help="rewrite backend/openapi.json from the composed api app",
    )
    parser.addoption(
        "--update-rules",
        action="store_true",
        help="rewrite the generated Prometheus rules from the declared objectives and monitors",
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


@pytest.fixture(autouse=True)
def uvicorn_access_logger() -> Iterator[None]:
    """uvicorn's access logger as it was before the test.

    uvicorn's settings detach that logger from the root when access lines are off, as every
    process of the backend wants; a server one test starts must not change what the logs of
    another test see.
    """
    access = logging.getLogger(UVICORN_ACCESS_LOGGER)
    handlers, propagate = list(access.handlers), access.propagate
    yield
    access.handlers[:] = handlers
    access.propagate = propagate


def harness_stopped(error: Exception) -> BaseException:
    """A short test failure without a traceback or an exception chain."""
    return pytest.fail.Exception(f"Харнесс тестовых баз остановлен:\n{error}", pytrace=False)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    """Print the claimed slot and what the claim restored, if the run used the databases."""
    for line in config.stash.get(RUN_SLOT_SUMMARY, []):
        terminalreporter.write_line(line)
