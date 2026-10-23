"""The life of a long-running process: start in steps, serve, drain on a signal, close (§3.11).

Start: settings and the production gate → logs, metrics, traces → the ops server (so
liveness answers and readiness says `starting` from here on) → the platform
(`platform.py`) → the role → the startup heap frozen for the garbage collector
(`core/runtime/heap.py`). A failed step exits with code 1 and one line naming it.

Stop on SIGTERM or SIGINT: readiness turns 503 at once → the role stops taking work and
drains it (in-flight requests, running tasks, the loops' current iteration) → the slices,
the clients and the engines close → the ops server stops → spans are exported and the log
queue written out. Every failure on the way is logged; none is suppressed, and the exit
code is then 1. The whole stop fits the container's stop grace period.

Work that ends by itself — a server or a worker that died — stops the process with code 1:
the orchestrator restarts it instead of keeping a process that looks alive and does nothing.
"""

import asyncio
from collections.abc import Collection, Mapping, Sequence
from contextlib import AsyncExitStack
from datetime import timedelta
from importlib.metadata import version
from typing import Final

import structlog

from shosai.composition.features import FEATURES
from shosai.composition.platform import open_platform
from shosai.composition.roles import Role
from shosai.composition.startup import (
    StartFailedError,
    load_process_settings,
    report_start_failure,
    start_step,
)
from shosai.composition.telemetry import ProcessTelemetry, open_telemetry
from shosai.core.config.loading import Settings
from shosai.core.config.roles import ProcessRole
from shosai.core.features import FeatureModule
from shosai.core.health.probes import DependencyProbe
from shosai.core.health.readiness import Readiness
from shosai.core.observability.debug_switches import following_debug_switches
from shosai.core.runtime.heap import freeze_startup_heap
from shosai.core.runtime.servers import HttpServer, server_config
from shosai.core.runtime.signals import stop_on_signals
from shosai.core.web.ops import build_ops_app

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
# Отсрочка между SIGTERM и SIGKILL у контейнера (F4 задаёт stop_grace_period столько же):
# слив роли (20 с), закрытие клиентов и выгрузка спанов (≤ 5 с) укладываются в неё.
STOP_GRACE_PERIOD: Final = timedelta(seconds=30)
OPS_DRAIN: Final = timedelta(seconds=2)
log = structlog.stdlib.get_logger(__name__)


async def run_process(
    role: ProcessRole,
    environ: Mapping[str, str],
    work: Role,
    features: Sequence[FeatureModule] = FEATURES,
) -> int:
    """Run one long-running role until a stop signal; return the exit code."""
    settings = load_process_settings(environ, role, features)
    if settings is None:
        return EXIT_FAILED
    async with open_telemetry(settings, role) as telemetry:
        log.info("Процесс запускается", version=version("shosai"))
        process = LongRunningProcess(settings, role, telemetry, features)
        with stop_on_signals(process.request_stop):
            code = await process.run(work)
        log.info("Процесс остановлен", exit_code=code)
        return code


class LongRunningProcess:
    """One process of a role: its readiness, its stop request and its run."""

    def __init__(
        self,
        settings: Settings,
        role: ProcessRole,
        telemetry: ProcessTelemetry,
        features: Sequence[FeatureModule],
    ) -> None:
        self.readiness = Readiness()
        self.stop = asyncio.Event()
        self._settings = settings
        self._role = role
        self._telemetry = telemetry
        self._features = features

    def request_stop(self) -> None:
        """Readiness turns 503 at once; the run then drains and closes."""
        self.readiness.drain()
        self.stop.set()

    async def run(self, work: Role) -> int:
        """Start in steps, serve until stopped, then close everything in reverse order."""
        try:
            async with AsyncExitStack() as stack:
                with start_step("ops"):
                    ops = await self._start_ops_server(stack)
                platform = await stack.enter_async_context(
                    open_platform(self._settings, self._role, self._telemetry, self._features)
                )
                debug = await stack.enter_async_context(
                    following_debug_switches(platform.services.valkey, self._telemetry.debug_logs)
                )
                with start_step("role"):
                    tasks = await stack.enter_async_context(work(platform, self._telemetry))
                freeze_startup_heap()
                return await serve_until_stopped(
                    self.readiness, self.stop, platform.probes, (*tasks, ops.task, debug)
                )
        except StartFailedError as error:
            report_start_failure(error)
            return EXIT_FAILED
        # Сбой работы или остановки: процесс уже закрыл всё, что смог; строка — со стеком.
        except Exception:
            log.exception("Процесс завершился с ошибкой")
            return EXIT_FAILED

    async def _start_ops_server(self, stack: AsyncExitStack) -> HttpServer:
        server = self._settings.server
        app = build_ops_app(self.readiness, self._telemetry.registry)
        ops = HttpServer(
            "ops",
            server_config(app, trusted_proxies=None, drain=OPS_DRAIN),
            str(server.bind_host),
            server.ops_port,
        )
        await ops.start()
        stack.push_async_callback(ops.stop)
        return ops


async def serve_until_stopped(
    readiness: Readiness,
    stop: asyncio.Event,
    probes: Sequence[DependencyProbe],
    work: Collection[asyncio.Task[None]],
) -> int:
    """Take work until asked to stop; work that ends by itself is a failure."""
    # Сигнал мог прийти ещё на старте: тогда процесс сразу уходит в слив.
    if not stop.is_set():
        readiness.ready(probes)
    stopping = asyncio.create_task(stop.wait(), name="stop-signal")
    done, _ = await asyncio.wait({stopping, *work}, return_when=asyncio.FIRST_COMPLETED)
    readiness.drain()
    if stopping in done:
        return EXIT_OK
    stopping.cancel()
    for task in done:
        log.critical("Работа процесса закончилась без сигнала остановки", task=task.get_name())
    return EXIT_FAILED
