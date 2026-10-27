"""The sweep's rule: when an open room is closed for idleness (MR-D1, meetings plan §1.2).

The sweep runs every 300 s as a singleton. It reads which rooms the SFU still holds and
decides per open room. A room the SFU holds is in use. A call still live in the rows while
the SFU no longer has its room lost its finish webhook: the sweep finishes it. A room empty
for 60 minutes since its last call finished — or since it was opened, if nobody ever came —
is closed, but never while its calendar event is still pending or its broadcast is live.
When the SFU cannot be read, the sweep closes nothing.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

SWEEP_EVERY: Final = timedelta(seconds=300)
IDLE_CLOSE_AFTER: Final = timedelta(minutes=60)


class SweepVerdict(StrEnum):
    """What the sweep does with an open room; the value is the metric's label."""

    KEEP_SFU_UNREACHABLE = "sfu_unreachable"
    KEEP_IN_USE = "in_use"
    FINISH_LOST_CALL = "finish_lost_call"
    KEEP_RECENT = "recent"
    KEEP_EVENT_PENDING = "event_pending"
    KEEP_BROADCAST_LIVE = "broadcast_live"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class IdleFacts:
    """What the sweep knows of one open room."""

    opened_at: datetime
    # SFU прочитан; иначе sweep ничего не закрывает.
    sfu_reachable: bool
    # SFU держит комнату: в ней кто-то есть или не истёк её собственный таймаут.
    in_sfu: bool
    # Последний звонок по строкам ещё идёт.
    call_live: bool
    # Когда SFU закончил последний звонок; None, если звонков не было.
    last_finished_at: datetime | None
    event_pending: bool
    broadcast_live: bool


def sweep_verdict(facts: IdleFacts, now: datetime) -> SweepVerdict:
    """The sweep's verdict on one open room at `now`: the first guard that holds, else close."""
    idle_since = facts.last_finished_at or facts.opened_at
    # Порядок важен: недоступный SFU не даёт ни закрыть комнату, ни закончить звонок.
    guards = (
        (not facts.sfu_reachable, SweepVerdict.KEEP_SFU_UNREACHABLE),
        (facts.in_sfu, SweepVerdict.KEEP_IN_USE),
        (facts.call_live, SweepVerdict.FINISH_LOST_CALL),
        (now - idle_since < IDLE_CLOSE_AFTER, SweepVerdict.KEEP_RECENT),
        (facts.event_pending, SweepVerdict.KEEP_EVENT_PENDING),
        (facts.broadcast_live, SweepVerdict.KEEP_BROADCAST_LIVE),
    )
    return next((verdict for holds, verdict in guards if holds), SweepVerdict.CLOSE)
