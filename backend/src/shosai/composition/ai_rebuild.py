"""`shosai ai rebuild-spend-counters`: the spend counters summed again from the cost rows.

Run at cutover (DATA_MAPPING E-3) and after Valkey came back empty (F6-D8). The command
opens both homes over the application role, checks them as a process start does, reads
the rows and rewrites the counters; a home out of reach stops it before anything is written.
"""

from collections.abc import Mapping
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from typing import Final

import structlog

from shosai.composition.features import FEATURES, feature_checks
from shosai.composition.startup import load_process_settings
from shosai.core.ai.spend.rebuild import (
    RebuildBusyError,
    RebuildUnsettledError,
    rebuild_spend_counters,
)
from shosai.core.config.loading import Settings
from shosai.core.config.roles import ProcessRole
from shosai.core.db.engines import HomeDatabases
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.home_checks import HomeGate, HomeState
from shosai.core.db.metrics import DatabaseMetrics
from shosai.core.db.migrations import MigrationHistory
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import REDIS_FAILURES, connect_redis
from shosai.core.observability.logs import configure_logging
from shosai.core.observability.metrics import ObservabilityMetrics, build_metrics_registry

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
log = structlog.stdlib.get_logger(__name__)


async def run_rebuild(environ: Mapping[str, str]) -> int:
    """Rebuild the counters; return the exit code."""
    role = ProcessRole.AI
    settings = load_process_settings(environ, role, feature_checks(FEATURES))
    if settings is None:
        return EXIT_FAILED
    registry = build_metrics_registry()
    pipeline = configure_logging(settings.observability, role, ObservabilityMetrics(registry))
    try:
        async with AsyncExitStack() as stack:
            return await _rebuilt(settings, stack)
    finally:
        pipeline.close()


async def _rebuilt(settings: Settings, stack: AsyncExitStack) -> int:
    registry = build_metrics_registry()
    databases = HomeDatabases.create(
        {home: settings.homes[home].database_url for home in Home}, ProcessRole.AI
    )
    stack.push_async_callback(databases.dispose)
    metrics = DatabaseMetrics(registry)
    gate = HomeGate(databases, MigrationHistory.load(), metrics)
    checks = await gate.verify_at_start()
    out_of_reach = [check.home.value for check in checks if check.state is not HomeState.VERIFIED]
    if out_of_reach:
        log.error("Пересборка не начата: дом недоступен", homes=out_of_reach)
        return EXIT_FAILED
    valkey = connect_redis(settings.shared_services.valkey_url, "shosai-ai-cli")
    stack.push_async_callback(valkey.aclose)
    try:
        await rebuild_spend_counters(
            HomeTransactions(databases, gate, metrics), valkey, datetime.now(UTC)
        )
    except HomeUnavailableError as error:
        log.error("Пересборка прервана: дом недоступен", home=error.home.value)
        return EXIT_FAILED
    except RebuildBusyError:
        log.error("Пересборка не начата: идёт другая пересборка")
        return EXIT_FAILED
    except RebuildUnsettledError:
        log.error("Пересборка не записана: строки поступали быстрее, чем читались")
        return EXIT_FAILED
    except REDIS_FAILURES as error:
        log.error("Пересборка не записана: Valkey недоступен", error_type=type(error).__name__)
        return EXIT_FAILED
    return EXIT_OK
