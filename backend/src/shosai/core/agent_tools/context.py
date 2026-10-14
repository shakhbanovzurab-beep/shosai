"""`ToolContext`: who a call acts for, until when, in which trace, with how much taint.

The scope is the principal's tenancy scope: a slice opens its own transaction under it, so
row-level security and the slice's access policy run inside the owner (inv-14). The
deadline is the turn's; a handler gives up when it passes. Taint grows within a run and
never falls (Leo §7.4): egress needs a card from `external`, memory ignores `suspicious`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from uuid import UUID

from shosai.core.kernel.tenancy import TenancyScope


class Taint(IntEnum):
    """How much untrusted text reached the run; ordered, so `>=` compares levels."""

    NONE = 0
    EXTERNAL = 1
    SUSPICIOUS = 2


@dataclass(frozen=True, slots=True)
class ToolContext:
    """The call's principal, deadline, trace and taint."""

    scope: TenancyScope
    run_id: UUID
    deadline: datetime
    taint: Taint = Taint.NONE
    trace_id: str | None = None

    def __post_init__(self) -> None:
        if self.scope.user_id is None:
            message = "инструмент агента вызывается только от имени человека"
            raise ValueError(message)
        if self.deadline.tzinfo is None:
            message = "срок вызова инструмента — время с часовым поясом"
            raise ValueError(message)

    def remaining_seconds(self, now: datetime | None = None) -> float:
        """Seconds left before the deadline; zero or less means the call is too late."""
        return (self.deadline - (now or datetime.now(UTC))).total_seconds()
