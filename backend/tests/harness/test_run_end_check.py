"""End-to-end check of ADR 0009: a run that leaves a trace in the schema fails and names it.

An inner pytest run with the harness fixtures starts as a subprocess and creates a
table without dropping it. Whoever claims the slot next drops the table: this test or a
parallel run that took the slot first.
"""

import asyncio
import os
import re
import sys
from pathlib import Path

from tests.harness.run_slot import prepare_run_slot
from tests.harness.settings import HarnessSettings
from tests.harness.slots import NoFreeSlotError, claim_slot
from whisperer.core.kernel.homes import Home

BACKEND = Path(__file__).resolve().parents[2]
INNER_CONFTEST = "from tests.conftest import harness_settings, pytest_terminal_summary, run_slot\n"
INNER_TEST = """
from whisperer.core.kernel.homes import Home


async def test_forgets_a_table(run_slot):
    connection = run_slot.claimed.connections[Home.EU]
    await connection.execute("CREATE TABLE harness_forgotten (id integer)")
"""
INNER_OPTIONS = (
    "-p",
    "no:cacheprovider",
    "-o",
    "asyncio_mode=auto",
    "-o",
    "asyncio_default_fixture_loop_scope=session",
    "-o",
    "asyncio_default_test_loop_scope=session",
)
FORGOTTEN_TABLE_SQL = "SELECT to_regclass('public.harness_forgotten')"
SLOT_LINE = re.compile(r"слот тестовых баз: whisperer_test_(\d+)")


async def run_inner_pytest(directory: Path) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pytest",
        *INNER_OPTIONS,
        "--rootdir",
        str(directory),
        str(directory),
        cwd=directory,
        env={**os.environ, "PYTHONPATH": str(BACKEND)},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    async with asyncio.timeout(120):
        output, _ = await process.communicate()
    return process.returncode or 0, output.decode()


async def test_a_run_that_leaves_a_table_fails_and_the_next_claim_drops_it(
    tmp_path: Path, harness_settings: HarnessSettings
) -> None:
    (tmp_path / "conftest.py").write_text(INNER_CONFTEST, encoding="utf-8")
    (tmp_path / "test_forgetful.py").write_text(INNER_TEST, encoding="utf-8")

    returncode, output = await run_inner_pytest(tmp_path)

    assert returncode != 0, output
    assert "Схема тестовых баз изменилась за прогон" in output, output
    assert "eu: + relation harness_forgotten" in output, output
    slot_line = SLOT_LINE.search(output)
    assert slot_line is not None, output
    try:
        claimed = await claim_slot(harness_settings, [int(slot_line.group(1))])
    except NoFreeSlotError:
        # Слот уже взял параллельный прогон, и его захват сам вернул слот в исходное состояние.
        return
    try:
        await prepare_run_slot(claimed)
        forgotten = await claimed.connections[Home.EU].fetchval(FORGOTTEN_TABLE_SQL)
    finally:
        await claimed.release()
    assert forgotten is None
