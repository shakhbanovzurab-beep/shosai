"""`shosai ai kill-switch`: the operator's kill switch before `studio`'s screen exists (F6-D5).

    shosai ai kill-switch engage --reason "…" [--hours 24]
    shosai ai kill-switch release
    shosai ai kill-switch status

One-shot: the command reads the settings, talks to Valkey only and writes one log line with
the outcome; the change itself is logged by the kill switch with `cli` as the operator.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final

import structlog

from shosai.composition.ai_spend import kill_switch
from shosai.composition.features import FEATURES
from shosai.composition.startup import load_process_settings
from shosai.core.ai.spend.kill_switch import KillSwitch
from shosai.core.config.roles import ProcessRole
from shosai.core.kv.connection import REDIS_FAILURES, connect_redis
from shosai.core.observability.logs import configure_logging
from shosai.core.observability.metrics import ObservabilityMetrics, build_metrics_registry

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
ACTOR: Final = "cli"
log = structlog.stdlib.get_logger(__name__)


class KillSwitchAction(StrEnum):
    """What `shosai ai kill-switch` does."""

    ENGAGE = "engage"
    RELEASE = "release"
    STATUS = "status"


@dataclass(frozen=True, slots=True)
class KillSwitchCommand:
    """The action, and for `engage` the reason and the hours it holds."""

    action: KillSwitchAction
    reason: str | None = None
    hours: float = 24.0


async def run_kill_switch(environ: Mapping[str, str], command: KillSwitchCommand) -> int:
    """Run the command; return the exit code."""
    role = ProcessRole.AI
    settings = load_process_settings(environ, role, FEATURES)
    if settings is None:
        return EXIT_FAILED
    pipeline = configure_logging(
        settings.observability, role, ObservabilityMetrics(build_metrics_registry())
    )
    valkey = connect_redis(settings.shared_services.valkey_url, "shosai-ai-cli")
    try:
        return await _switched(kill_switch(settings.spend, valkey), command)
    finally:
        await valkey.aclose()
        pipeline.close()


async def _switched(switch: KillSwitch, command: KillSwitchCommand) -> int:
    try:
        match command.action:
            case KillSwitchAction.ENGAGE:
                await switch.engage(ACTOR, command.reason or "", timedelta(hours=command.hours))
            case KillSwitchAction.RELEASE:
                await switch.release(ACTOR)
            case KillSwitchAction.STATUS:
                pass
        state = await switch.state()
    except ValueError as error:
        log.error("Команда выключателя отклонена", reason=str(error))
        return EXIT_FAILED
    except REDIS_FAILURES as error:
        log.error("Valkey недоступен: выключатель не изменён", error_type=type(error).__name__)
        return EXIT_FAILED
    log.info(
        "Состояние аварийного выключателя ИИ", engaged=state.engaged, by_setting=state.by_setting,
        actor=state.actor, reason=state.reason,
        left_seconds=int(state.left.total_seconds()) if state.left else None,
    )  # fmt: skip
    return EXIT_OK
