"""A backend role started as its own process, the way a container runs it.

The console script `shosai` of this environment runs with exactly the variables the
test gives and real signals; its JSON lines go to a file the test reads. Every wait is
bounded, and a process still running when the test ends is killed.
"""

import asyncio
import json
import signal
import sys
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.harness.process_environ import LOOPBACK

SHOSAI = Path(sys.executable).with_name("shosai")
READY_WAIT_SECONDS = 30.0
POLL_SECONDS = 0.1
# Меньше отсрочки остановки контейнера (composition/process.py): слив обязан в неё уложиться.
STOP_WAIT_SECONDS = 25.0
REQUEST_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class RoleProcess:
    """A running role: its process, its ports and the file its log lines go to."""

    process: asyncio.subprocess.Process
    log_path: Path
    environ: Mapping[str, str]

    def port(self, variable: str) -> int:
        """The port the process was given in `HTTP_PORT` or `OPS_PORT`."""
        return int(self.environ[variable])

    def lines(self) -> list[dict[str, Any]]:
        """Every log line written so far; a line that is not JSON fails the test."""
        return read_lines(self.log_path)

    async def get(self, variable: str, path: str) -> httpx.Response:
        """A GET to one of the process's ports on loopback."""
        url = f"http://{LOOPBACK}:{self.port(variable)}{path}"
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            return await client.get(url)

    async def wait_ready(self) -> dict[str, Any]:
        """The readiness body once the process answers 200; fails if it exits or never does."""
        deadline = time.monotonic() + READY_WAIT_SECONDS
        while time.monotonic() < deadline:
            if self.process.returncode is not None:
                pytest.fail(f"процесс вышел с кодом {self.process.returncode}:\n{self.tail()}")
            try:
                response = await self.get("OPS_PORT", "/readyz")
            except httpx.TransportError:
                response = None
            if response is not None and response.status_code == 200:
                body: dict[str, Any] = response.json()
                return body
            await asyncio.sleep(POLL_SECONDS)
        pytest.fail(f"процесс не стал готов за {READY_WAIT_SECONDS} с:\n{self.tail()}")

    async def stop(self) -> int:
        """SIGTERM, then the exit code once the process has drained and closed."""
        self.process.send_signal(signal.SIGTERM)
        return await self.wait_exit()

    async def wait_exit(self) -> int:
        """The exit code of a process that ends by itself within the bound."""
        try:
            return await asyncio.wait_for(self.process.wait(), STOP_WAIT_SECONDS)
        except TimeoutError:
            pytest.fail(f"процесс не завершился за {STOP_WAIT_SECONDS} с:\n{self.tail()}")

    def tail(self) -> str:
        """The last lines of the log, for a failure message."""
        return "\n".join(self.log_path.read_text(encoding="utf-8").splitlines()[-20:])


def read_lines(path: Path) -> list[dict[str, Any]]:
    """The JSON lines of a log file."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def messages(lines: Sequence[dict[str, Any]]) -> list[str]:
    """The message of every line, in order."""
    return [str(line["message"]) for line in lines]


@asynccontextmanager
async def role_process(
    arguments: Sequence[str], environ: Mapping[str, str], log_path: Path
) -> AsyncIterator[RoleProcess]:
    """`shosai <arguments>` with exactly `environ`; killed if still running after the block."""
    with log_path.open("wb") as log_file:
        process = await asyncio.create_subprocess_exec(
            SHOSAI, *arguments, env=dict(environ), stdout=log_file, stderr=log_file
        )
    try:
        yield RoleProcess(process, log_path, environ)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def run_command(
    arguments: Sequence[str], environ: Mapping[str, str], log_path: Path
) -> tuple[int, list[dict[str, Any]]]:
    """A one-shot command: its exit code and its log lines."""
    async with role_process(arguments, environ, log_path) as running:
        code = await running.wait_exit()
    return code, read_lines(log_path)
