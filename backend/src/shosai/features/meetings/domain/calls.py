"""A call: one life of a room in the SFU, from its first participant until it finishes.

LiveKit tells the API about a room instance through webhooks keyed by the instance's sid:
`room_started`, `participant_joined`, `participant_left`, `room_finished` (after its own
departure timeout of 60 s). Webhooks arrive late, twice or out of order, and any of them
may be lost; the sweep covers a lost finish. So a call is folded from what was seen, and
the fold is the same in any order and under replays: it starts at the earliest event seen,
its peak is the most participants seen, and it ends once — at the finish. After the finish
meetings hands the call over to notes (B2, B3) and only then is the call ended; a rejoin
within the hour is a new call of the same room.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class CallState(StrEnum):
    """Where a call stands."""

    LIVE = "live"
    # SFU закончил комнату; передача заметкам ещё идёт.
    ENDING = "ending"
    ENDED = "ended"


@dataclass(frozen=True, slots=True)
class Call:
    """A call as the rules see it."""

    id: UUID
    room_id: UUID
    lk_room_sid: str
    state: CallState
    started_at: datetime
    peak_participants: int = 0
    emptied_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def is_live(self) -> bool:
        """Whether people may still be in the call."""
        return self.state is CallState.LIVE

    def seconds(self) -> int:
        """How long the call lasted, from its start to its finish; zero while it goes on."""
        if self.emptied_at is None:
            return 0
        return max(0, int((self.emptied_at - self.started_at).total_seconds()))


def opened(call_id: UUID, room_id: UUID, lk_room_sid: str, at: datetime) -> Call:
    """The call the first event of an SFU room instance opens."""
    return Call(
        id=call_id, room_id=room_id, lk_room_sid=lk_room_sid, state=CallState.LIVE, started_at=at
    )


def seen(call: Call, at: datetime, participants: int | None = None) -> Call:
    """The call after any event of its instance: the earliest start, the largest count."""
    peak = (
        call.peak_participants
        if participants is None
        else max(call.peak_participants, participants)
    )
    return replace(call, started_at=min(call.started_at, at), peak_participants=peak)


def finished(call: Call, at: datetime) -> Call:
    """The call once the SFU finished its room; a second finish changes nothing.

    The finish counts as an event of the instance too, so the start is the earliest of all of
    them whichever came first.
    """
    call = seen(call, at)
    if call.state is not CallState.LIVE:
        return call
    return replace(call, state=CallState.ENDING, emptied_at=at)


def handed_over(call: Call, at: datetime) -> Call:
    """The call after its chat, board and tracks went to notes; only a finished call ends."""
    if call.state is not CallState.ENDING:
        return call
    return replace(call, state=CallState.ENDED, ended_at=at)
