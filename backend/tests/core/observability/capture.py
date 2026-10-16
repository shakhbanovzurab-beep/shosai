"""A logging pipeline writing into memory, for tests of what reaches the log lines."""

import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from prometheus_client import CollectorRegistry

from shosai.core.config.roles import ProcessRole
from shosai.core.config.sections import ObservabilitySettings
from shosai.core.config.values import LogLevel
from shosai.core.observability.debug_logs import DebugLogGate
from shosai.core.observability.logs import configure_logging
from shosai.core.observability.metrics import ObservabilityMetrics


@dataclass(frozen=True, slots=True)
class CapturedLogs:
    """Output of a pipeline; complete once the `captured_logs` block has ended."""

    stream: io.StringIO
    registry: CollectorRegistry
    # Фильтр отладочных строк конвейера: тест включает переключатели через него.
    debug_logs: DebugLogGate

    def text(self) -> str:
        """Everything written, exactly as a log collector would read it."""
        return self.stream.getvalue()

    def lines(self) -> list[dict[str, Any]]:
        """Every line parsed as JSON; a line that is not JSON fails the test."""
        return [json.loads(line) for line in self.text().splitlines()]


@contextmanager
def captured_logs(
    level: LogLevel = LogLevel.INFO, role: ProcessRole = ProcessRole.API
) -> Iterator[CapturedLogs]:
    """Configure the real pipeline over memory; on exit the queued lines are written out."""
    registry = CollectorRegistry()
    stream = io.StringIO()
    pipeline = configure_logging(
        ObservabilitySettings(log_level=level), role, ObservabilityMetrics(registry), stream
    )
    captured = CapturedLogs(stream, registry, pipeline.debug_logs)
    try:
        yield captured
    finally:
        pipeline.close()
