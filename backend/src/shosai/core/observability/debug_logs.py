"""DEBUG lines for one user or one company while their switch is on (§16.7, F5 plan §3.13).

The gate is a filter on the process's log handler. Without a switch it lets every line of
the configured level through and nothing else changes. While a switch is on, Shosai's own
loggers (`shosai.*`) go to DEBUG — never the libraries': their debug lines carry SQL
parameters, request bodies and headers (§16.8) — and a line under the configured level
passes only when its user or company is switched on and the switch has not ended. The end
is checked on every such line, so the lines stop at the switch's end even between two
refreshes of the switches.
"""

import logging
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Final
from uuid import UUID

from structlog.contextvars import get_contextvars

from shosai.core.observability.log_context import late_fields

OWN_LOGGERS: Final = "shosai"
EMPTY: Final[Mapping[str, float]] = MappingProxyType({})


class DebugScope(StrEnum):
    """Whose lines a switch opens: one account's or one company's."""

    USER = "user"
    ORG = "org"

    @property
    def log_key(self) -> str:
        """The log field that names the account or the company."""
        return f"{self.value}_id"


@dataclass(frozen=True, slots=True)
class DebugSwitch:
    """DEBUG lines of one account or one company until `ends_at`."""

    scope: DebugScope
    target: UUID
    ends_at: datetime


class DebugLogGate(logging.Filter):
    """Lets a line under the configured level through only for a switched-on user or company."""

    def __init__(self, configured_level: int = logging.INFO) -> None:
        super().__init__()
        self._configured_level = configured_level
        # Словари заменяются целиком: фильтр читает их из потоков без блокировки.
        self._ends: Mapping[DebugScope, Mapping[str, float]] = MappingProxyType(
            dict.fromkeys(DebugScope, EMPTY)
        )

    def apply(self, switches: Iterable[DebugSwitch]) -> None:
        """Open the lines of these switches; Shosai's loggers go to DEBUG while any is on."""
        ends: dict[DebugScope, dict[str, float]] = {scope: {} for scope in DebugScope}
        for switch in switches:
            ends[switch.scope][str(switch.target)] = switch.ends_at.timestamp()
        self._ends = MappingProxyType({scope: MappingProxyType(ids) for scope, ids in ends.items()})
        if self._configured_level > logging.DEBUG:
            on = any(ends.values())
            logging.getLogger(OWN_LOGGERS).setLevel(logging.DEBUG if on else logging.NOTSET)

    def close(self) -> None:
        """Back to the configured level."""
        self.apply(())

    def filter(self, record: logging.LogRecord) -> bool:
        """True for a line of the configured level, or of a switched-on user or company."""
        if record.levelno >= self._configured_level:
            return True
        fields = record_fields(record)
        now = time.time()
        for scope, ends in self._ends.items():
            target = fields.get(scope.log_key)
            if isinstance(target, str) and ends.get(target, 0.0) > now:
                return True
        return False


def record_fields(record: logging.LogRecord) -> Mapping[str, object]:
    """The ids the line will carry: its own fields, then the bound and the late ones."""
    fields: dict[str, object] = {}
    for key, value in late_fields().items():
        fields[key] = str(value)
    fields.update(get_contextvars())
    # У строк structlog событие — словарь; явные поля строки главнее контекста.
    if isinstance(record.msg, dict):
        fields.update({key: str(value) for key, value in record.msg.items()})
    return fields
