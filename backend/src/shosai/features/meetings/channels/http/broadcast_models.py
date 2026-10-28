"""The broadcast routes' contract: what the host and the link send and get (MR-D7, A12b)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shosai.features.meetings.application.broadcast_chat import BroadcastMessage
from shosai.features.meetings.application.broadcast_entry import Ticket
from shosai.features.meetings.application.broadcast_stage import BroadcastStateView
from shosai.features.meetings.domain.broadcasts import BroadcastEntry, BroadcastState, StageRole
from shosai.features.meetings.domain.chat import HISTORY_PAGE_MAX, TEXT_MAX
from shosai.features.meetings.domain.principals import NAME_MAX
from shosai.features.meetings.domain.rooms import TITLE_MAX


class Strict(BaseModel):
    """A request body: a field the contract does not know is refused."""

    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    """A response shape: every field is always sent."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class NewBroadcast(Strict):
    """A broadcast's title and whether viewers wait to be let in."""

    title: str = Field(max_length=TITLE_MAX * 2)
    waiting_room: bool = False


class BroadcastOut(Out):
    """The host's broadcast and its link."""

    id: UUID
    title: str
    link: str = Field(description="The link the stage and the audience open.")
    state: BroadcastState
    waiting_room: bool


class LiveJoinIn(Strict):
    """A guest's name; a signed-in person comes under their profile's name."""

    name: str | None = Field(default=None, max_length=NAME_MAX * 2)


class LiveKnockIn(Strict):
    """The knock the waiting room gave."""

    knock: str = Field(min_length=1, max_length=64)


class LiveTicketOut(Out):
    """What the link answers: where to go and, when let in, the passes."""

    entry: BroadcastEntry
    title: str
    role: StageRole | None
    waiting_room: bool
    identity: str | None
    livekit_url: str | None
    livekit_token: str | None
    room_pass: str | None
    knock: str | None = Field(description="Ask again with it while `entry` is `wait`.")


class LiveMemberOut(Out):
    """A place on the stage; `identity` is its session now, null when nobody holds it."""

    principal: str
    identity: str | None
    name: str
    role: StageRole
    on_air: bool


class LiveHandOut(Out):
    """A viewer asking to speak."""

    principal: str
    name: str
    at: datetime
    invited: bool


class LiveKnockOut(Out):
    """A viewer waiting to be let in."""

    id: str
    name: str
    at: datetime


class LiveStateOut(Out):
    """The broadcast as its reader sees it; the queues only for the host and co-hosts."""

    status: BroadcastState
    title: str
    role: StageRole | None
    members: list[LiveMemberOut]
    viewers: int | None = Field(description="Null when LiveKit does not answer.")
    waiting_room: bool
    hands: list[LiveHandOut]
    admissions: list[LiveKnockOut]
    hand: Literal["down", "raised", "invited"]
    started_at: datetime | None


class LiveChatIn(Strict):
    """A message's text, 1 to 2 000 characters once trimmed."""

    text: str = Field(max_length=TEXT_MAX * 2)


class LiveChatMessageOut(Out):
    """A message of the broadcast; the stage's are marked."""

    seq: int
    author: str
    text: str
    from_stage: bool
    mine: bool
    sent_at: datetime


class LiveChatPageOut(Out):
    """Messages after a number; a non-null `next_cursor` is the `after` of the next page."""

    items: list[LiveChatMessageOut]
    next_cursor: str | None


class LiveHandIn(Strict):
    """Raise or lower your hand."""

    raised: bool


class LiveInviteIn(Strict):
    """Invite the hand's viewer to the stage, or decline the hand."""

    invite: bool


class LiveAdmitIn(Strict):
    """Let the knock in, or turn it away."""

    admitted: bool


class LiveSeatIn(Strict):
    """What changes about a place: on air or not, co-host or speaker."""

    on_air: bool | None = None
    role: Literal["cohost", "speaker"] | None = None


PAGE_MAX = HISTORY_PAGE_MAX


def ticket_out(ticket: Ticket) -> LiveTicketOut:
    """The contract's shape of a ticket."""
    return LiveTicketOut(
        entry=ticket.entry, title=ticket.title, role=ticket.role, waiting_room=ticket.waiting_room,
        identity=ticket.identity, livekit_url=ticket.livekit_url,
        livekit_token=ticket.livekit_token, room_pass=ticket.room_pass, knock=ticket.knock,
    )  # fmt: skip


def state_out(view: BroadcastStateView) -> LiveStateOut:
    """The contract's shape of a state."""
    return LiveStateOut(
        status=view.status, title=view.title, role=view.role, viewers=view.viewers,
        members=[
            LiveMemberOut(principal=seat.principal, identity=seat.identity, name=seat.name,
                          role=seat.role, on_air=seat.on_air)
            for seat in view.members
        ],
        waiting_room=view.waiting_room,
        hands=[
            LiveHandOut(principal=hand.principal, name=hand.name, at=hand.at, invited=hand.invited)
            for hand in view.hands
        ],
        admissions=[
            LiveKnockOut(id=knock.id, name=knock.name, at=knock.at) for knock in view.admissions
        ],
        hand=view.hand, started_at=view.started_at,
    )  # fmt: skip


def message_out(message: BroadcastMessage, principal: str) -> LiveChatMessageOut:
    """The contract's shape of a message, marked as the reader's own."""
    return LiveChatMessageOut(
        seq=message.seq, author=message.author, text=message.text, from_stage=message.from_stage,
        mine=message.principal == principal, sent_at=message.sent_at,
    )  # fmt: skip
