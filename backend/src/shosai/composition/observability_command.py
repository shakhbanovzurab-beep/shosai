"""`shosai observability debug`: DEBUG lines of one account or company for a while (§16.7).

    shosai observability debug --user ID --reason "…" [--minutes 15]
    shosai observability debug --org ID --reason "…" [--minutes 15]
    shosai observability debug --user ID --off
    shosai observability debug                          # the switches that are on

One-shot: the command reads the settings, talks to Valkey only and logs who asked, why and
the switches that are on afterwards. Every process picks a change up within 15 s.
"""

import getpass
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import structlog

from shosai.composition.features import FEATURES
from shosai.composition.startup import load_process_settings
from shosai.core.config.roles import ProcessRole
from shosai.core.kv.connection import REDIS_FAILURES, connect_redis
from shosai.core.observability.debug_logs import DebugScope
from shosai.core.observability.debug_switches import DebugSwitches
from shosai.core.observability.logs import configure_logging
from shosai.core.observability.metrics import ObservabilityMetrics, build_metrics_registry

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
REASON_MAX: Final = 200
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DebugCommand:
    """Whose lines, for how long and why; `off` ends the switch; no target only lists."""

    scope: DebugScope | None = None
    target: UUID | None = None
    minutes: int = 15
    reason: str | None = None
    off: bool = False


async def run_debug_switch(environ: Mapping[str, str], command: DebugCommand) -> int:
    """Run the command; return the exit code."""
    role = ProcessRole.OBSERVABILITY
    settings = load_process_settings(environ, role, FEATURES)
    if settings is None:
        return EXIT_FAILED
    pipeline = configure_logging(
        settings.observability, role, ObservabilityMetrics(build_metrics_registry())
    )
    valkey = connect_redis(settings.shared_services.valkey_url, "shosai-observability-cli")
    try:
        return await switched(DebugSwitches(valkey), command, getpass.getuser())
    finally:
        await valkey.aclose()
        pipeline.close()


async def switched(switches: DebugSwitches, command: DebugCommand, actor: str) -> int:
    """Apply the command and log the switches that are on."""
    try:
        await apply(switches, command, actor)
        active = await switches.active(datetime.now(UTC))
    except ValueError as error:
        log.error("Команда отладки отклонена", reason=str(error))
        return EXIT_FAILED
    except REDIS_FAILURES as error:
        log.error("Valkey недоступен: отладка не изменена", error_type=type(error).__name__)
        return EXIT_FAILED
    log.info(
        "Включённые отладочные журналы",
        switches=[
            f"{each.scope.value}:{each.target} до {each.ends_at:%H:%M} UTC" for each in active
        ],
    )
    return EXIT_OK


async def apply(switches: DebugSwitches, command: DebugCommand, actor: str) -> None:
    """Switch on or off; nothing without a target."""
    if command.scope is None or command.target is None:
        return
    target = {command.scope.log_key: str(command.target)}
    if command.off:
        ended = await switches.switch_off(command.scope, command.target)
        log.info("Отладка выключена оператором", actor=actor, was_on=ended, **target)
        return
    reason = (command.reason or "").strip()
    if not reason or len(reason) > REASON_MAX:
        message = f"нужна причина длиной до {REASON_MAX} символов"
        raise ValueError(message)
    duration = timedelta(minutes=command.minutes)
    switch = await switches.switch_on(command.scope, command.target, duration, datetime.now(UTC))
    log.info("Отладка включена оператором", actor=actor, reason=reason,
             ends_at=switch.ends_at.isoformat(), **target)  # fmt: skip
