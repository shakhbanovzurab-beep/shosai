"""Time and size limits of the outbox relay (target architecture §12)."""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class RelayLimits:
    """Rows per pass, the lease of a claim and the longest pause before a retry.

    100 rows every 5 seconds is the relay's designed limit of 20 events per second (§12);
    a lasting load above it is the revisit trigger of the outbox design.
    """

    batch: int = 100
    lease: timedelta = timedelta(seconds=30)
    longest_pause: timedelta = timedelta(seconds=300)

    def __post_init__(self) -> None:
        if self.batch < 1 or self.lease <= timedelta(0) or self.longest_pause <= timedelta(0):
            message = "relay: пачка от одной строки, аренда и пауза больше нуля"
            raise ValueError(message)
