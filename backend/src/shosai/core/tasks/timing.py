"""Time limits of task delivery: lease, renewal, recovery, blocking reads and retry backoff.

A delivered message stays in the consumer's pending list until it is settled. A live
worker renews the lease of every message it holds, so only a message of a dead worker —
or one sent back for a retry — is idle longer than the lease and is claimed again (§4.3).
"""

import secrets
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final

# Повтор раньше половины паузы не уходит: задачи, упавшие в одну секунду, расходятся.
JITTER_FLOOR: Final = 0.5
JITTER_STEPS: Final = 1000


@dataclass(frozen=True, slots=True)
class Backoff:
    """Pause before the next delivery: `first`, doubling with each failure, up to `ceiling`.

    The pause is shortened at random to 50 to 100%, never to zero: an instant retry would
    burn every delivery within a second of a network outage (draft lesson).
    """

    first: timedelta = timedelta(seconds=5)
    ceiling: timedelta = timedelta(seconds=120)

    def __post_init__(self) -> None:
        if not timedelta(0) < self.first <= self.ceiling:
            message = "пауза повтора: первая больше нуля и не больше предельной"
            raise ValueError(message)

    def delay(self, failed_delivery: int) -> timedelta:
        """The pause after delivery number `failed_delivery` failed."""
        if failed_delivery < 1:
            message = "номер выдачи начинается с 1"
            raise ValueError(message)
        # Степень ограничена: дальше предела удвоение ничего не меняет.
        exponent = min(failed_delivery - 1, 16)
        base = min(self.first * (1 << exponent), self.ceiling)
        share = (
            JITTER_FLOOR + (1 - JITTER_FLOOR) * secrets.randbelow(JITTER_STEPS + 1) / JITTER_STEPS
        )
        return base * share


@dataclass(frozen=True, slots=True)
class StreamTiming:
    """Delivery time limits of one queue; production uses the defaults (§4.3)."""

    # Сообщение без продления дольше аренды считается брошенным и выдаётся снова.
    lease: timedelta = timedelta(seconds=120)
    # Восемь продлений на одну аренду: воркер, задумавшийся на секунды, не теряет сообщения.
    renew_every: timedelta = timedelta(seconds=15)
    recover_every: timedelta = timedelta(seconds=5)
    # Управляемый Valkey рвёт блокирующее чтение на пятой секунде (урок черновика).
    read_block: timedelta = timedelta(seconds=2)
    # Пауза после сбоя Valkey: без неё обрыв превращается в цикл переподключений.
    outage_pause: timedelta = timedelta(seconds=1)
    prune_consumers_every: timedelta = timedelta(minutes=5)
    consumer_stale_after: timedelta = timedelta(minutes=5)
    backoff: Backoff = field(default_factory=Backoff)

    def __post_init__(self) -> None:
        if not self.renew_every < self.lease:
            message = "продление аренды должно быть чаще её срока"
            raise ValueError(message)
        if self.backoff.ceiling > self.lease:
            message = "пауза повтора не длиннее аренды: повтор назначается через простой сообщения"
            raise ValueError(message)
