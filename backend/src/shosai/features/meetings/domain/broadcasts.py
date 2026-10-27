"""A broadcast: a stage that speaks and an audience that watches (MR-D7, SM-8).

The stage — the host, co-hosts and at most 10 speakers besides the host — gathers before
the broadcast starts; the audience gets in only while it is live, up to 100 viewers, through
the waiting room only when the host turns it on. A viewer publishes nothing, not even data
packets: chat, reactions and a raised hand go through meetings' routes, where bans and rates
are checked, and the SFU hides viewers from each other. Rights are computed by one function
for the join, a move onto the stage and a return to the air, so they never drift apart.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final

from shosai.features.meetings.domain.joining import Grants

VIEWERS_MAX: Final = 100
SPEAKERS_MAX: Final = 10
KNOCK_TTL: Final = timedelta(minutes=10)
HAND_TTL: Final = timedelta(minutes=20)
CHAT_WINDOW_SECONDS: Final = 10
CHAT_BURST_AUDIENCE: Final = 5
CHAT_BURST_STAGE: Final = 20
REACTION_WINDOW_SECONDS: Final = 10
REACTION_BURST: Final = 10
TOPIC: Final = "stream"

ON_STAGE: Final = Grants(can_publish=True, can_publish_data=True, can_update_own_metadata=True)
# Убранный из эфира спикер остаётся на сцене, но его дорожки закрыты грантом.
OFF_AIR: Final = Grants(can_publish=False, can_publish_data=True, can_update_own_metadata=True)
AUDIENCE: Final = Grants(
    can_publish=False, can_publish_data=False, can_update_own_metadata=False, hidden=True
)


class BroadcastState(StrEnum):
    """Where a broadcast stands."""

    SCHEDULED = "scheduled"
    LIVE = "live"
    ENDED = "ended"


class StageRole(StrEnum):
    """A part on the stage; the audience has none."""

    HOST = "host"
    COHOST = "cohost"
    SPEAKER = "speaker"


class BroadcastEntry(StrEnum):
    """What the broadcast's link answers someone."""

    STAGE = "stage"
    AUDIENCE = "audience"
    WAIT = "wait"
    NOT_LIVE = "not_live"
    FULL = "full"
    ENDED = "ended"


_NEXT: Final = {
    BroadcastState.SCHEDULED: frozenset({BroadcastState.LIVE, BroadcastState.ENDED}),
    BroadcastState.LIVE: frozenset({BroadcastState.ENDED}),
    BroadcastState.ENDED: frozenset[BroadcastState](),
}


@dataclass(frozen=True, slots=True)
class EntryFacts:
    """What the link knows of a broadcast and of the one who opened it."""

    state: BroadcastState
    role: StageRole | None
    waiting_room: bool
    viewers: int


def may_move(current: BroadcastState, target: BroadcastState) -> bool:
    """Whether a broadcast may move from one state to another."""
    return target in _NEXT[current]


def grants_for(role: StageRole | None, *, on_air: bool = True) -> Grants:
    """What a session may do in the SFU: the stage speaks, the audience only watches."""
    if role is None:
        return AUDIENCE
    return ON_STAGE if on_air else OFF_AIR


def entry(facts: EntryFacts) -> BroadcastEntry:
    """What the link answers: the stage always gets in before the end, the audience only live."""
    if facts.state is BroadcastState.ENDED:
        return BroadcastEntry.ENDED
    if facts.role is not None:
        return BroadcastEntry.STAGE
    if facts.state is not BroadcastState.LIVE:
        return BroadcastEntry.NOT_LIVE
    if facts.viewers >= VIEWERS_MAX:
        return BroadcastEntry.FULL
    return BroadcastEntry.WAIT if facts.waiting_room else BroadcastEntry.AUDIENCE


def may_moderate(role: StageRole | None) -> bool:
    """The host and co-hosts manage the stage, the queues and the chat."""
    return role in {StageRole.HOST, StageRole.COHOST}


def may_manage_cohosts(role: StageRole | None) -> bool:
    """Only the host names and removes co-hosts, so the right cannot be taken from them."""
    return role is StageRole.HOST


def chat_burst(role: StageRole | None) -> int:
    """How many messages a sender may send per window: the stage answers, the audience asks."""
    return CHAT_BURST_AUDIENCE if role is None else CHAT_BURST_STAGE


def stage_has_room(speakers: int) -> bool:
    """Whether one more speaker fits on the stage besides the host."""
    return speakers < SPEAKERS_MAX
