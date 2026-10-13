"""Time and size limits of the outbox relay (target architecture §12)."""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class RelayLimits:
    """Rows per pass, the drain budget of a tick, the lease of a claim, the longest pause.

    A tick runs passes of 100 rows while each claims a full batch, and starts no pass once
    15 s have gone: the last pass then ends before the relay task's deadline (25 s), and
    every pass before the lease of its rows (30 s) ends. A tick cut by the budget means a
    load above what the relay drains, the revisit trigger of the outbox design (§12).
    """

    batch: int = 100
    drain_budget: timedelta = timedelta(seconds=15)
    lease: timedelta = timedelta(seconds=30)
    longest_pause: timedelta = timedelta(seconds=300)

    def __post_init__(self) -> None:
        positive = (self.drain_budget, self.lease, self.longest_pause)
        if self.batch < 1 or any(value <= timedelta(0) for value in positive):
            message = "relay: пачка от одной строки, бюджет, аренда и пауза больше нуля"
            raise ValueError(message)
        if self.drain_budget >= self.lease:
            message = "relay: бюджет тика короче аренды строк"
            raise ValueError(message)
