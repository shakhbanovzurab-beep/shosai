"""The start of a process, step by step: a failed step stops the start and is named (§3.11).

Settings come first, before logging exists: a rejected configuration is reported through
a pipeline with the default level, so even that failure is one JSON line on stdout.
"""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager

import structlog
from prometheus_client import CollectorRegistry

from whisperer.core.config.gate import (
    ProductionCheck,
    UnsafeConfigurationError,
    enforce_production_gate,
)
from whisperer.core.config.loading import ConfigurationError, Settings, load_settings
from whisperer.core.config.roles import ProcessRole
from whisperer.core.config.sections import ObservabilitySettings
from whisperer.core.observability.logs import configure_logging
from whisperer.core.observability.metrics import ObservabilityMetrics

SETTINGS_STEP = "settings"
log = structlog.stdlib.get_logger(__name__)


class StartFailedError(Exception):
    """A start step failed; the cause is chained, the step is named."""

    def __init__(self, step: str) -> None:
        self.step = step
        super().__init__(f"старт остановлен на шаге {step}")


@contextmanager
def start_step(step: str) -> Iterator[None]:
    """Turn any failure of the block into `StartFailedError` naming the step."""
    try:
        yield
    except StartFailedError:
        raise
    except Exception as error:
        raise StartFailedError(step) from error


def report_start_failure(error: StartFailedError) -> None:
    """One critical line naming the step, with the cause and its stack."""
    log.critical("Процесс не стартовал", step=error.step, exc_info=error.__cause__)


def load_process_settings(
    environ: Mapping[str, str], role: ProcessRole, checks: Sequence[ProductionCheck]
) -> Settings | None:
    """The settings that passed the production gate, or None after one line naming why."""
    try:
        settings = load_settings(environ)
        enforce_production_gate(settings, checks)
    except (ConfigurationError, UnsafeConfigurationError) as error:
        with _default_logging(role):
            # Текст ошибки называет переменные и причины, но не значения.
            log.critical("Процесс не стартовал", step=SETTINGS_STEP, reason=str(error))
        return None
    return settings


@contextmanager
def _default_logging(role: ProcessRole) -> Iterator[None]:
    pipeline = configure_logging(
        ObservabilitySettings(), role, ObservabilityMetrics(CollectorRegistry())
    )
    try:
        yield
    finally:
        pipeline.close()
