"""Leo's `meetings` toolset as the model sees it: the person's own Shosai calls (MR-D8).

One read lists the person's rooms with a call going on; two writes start a call in a new room
of the person's Personal space and end one of their calls for everyone — each only after the
person approves its card. The results carry the person's own titles and the room's links, so
they have no provenance label.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shosai.core.agent_tools.spec import Reversibility, ToolEffect, ToolSpec
from shosai.features.meetings.channels import agent_words as words
from shosai.features.meetings.domain.rooms import TITLE_MAX

TOOLSET: Final = "meetings"
# Домен запросов кабинета, который перечитывается после записи: раздел «Встречи».
MEETINGS_DOMAIN: Final = ("meetings",)


class Strict(BaseModel):
    """Arguments the model sends: a field the schema lacks is refused."""

    model_config = ConfigDict(extra="forbid")


class NoArguments(Strict):
    """Nothing to choose."""


class LiveCall(BaseModel):
    """One of the person's rooms with a call going on."""

    room_id: UUID
    title: str | None = Field(description="Null for an untitled room.")
    invite_link: str = Field(description="The link anyone uses to join; share it as is.")
    started_at: datetime
    participants: int | None = Field(description="How many are in the call; null when unknown.")
    notes_on: bool = Field(description="Leo takes notes of the call.")


class LiveCalls(BaseModel):
    """The person's calls going on now, the latest first."""

    calls: list[LiveCall]


class StartCall(Strict):
    """A call to start now in a new room of the user's Personal space."""

    title: str | None = Field(
        default=None, max_length=TITLE_MAX,
        description="The meeting's title in the user's words; omit it when they gave none.",
    )  # fmt: skip


class CallStarted(BaseModel):
    """The room made; the user joins it by its link."""

    room_id: UUID
    invite_link: str = Field(description="The link to join and to share with others.")
    join_path: str = Field(description="The room's page in the cabinet, for navigate.")


class EndCall(Strict):
    """One of the user's rooms to end for everyone."""

    room_id: UUID = Field(description="A room from meetings.list_live.")


class CallEnded(BaseModel):
    """The room is closed for good; its link no longer works."""

    ended: bool = True


LIST_LIVE: Final = ToolSpec(
    name="meetings.list_live",
    toolset=TOOLSET,
    description=(
        "List the user's own Shosai meeting rooms where a call is going on now: title, invite "
        "link, start time, how many are in the call and whether Leo takes notes. Meetings in "
        "Google Meet, Zoom or Teams are not here."
    ),
    input=NoArguments,
    output=LiveCalls,
    effect=ToolEffect.READ,
    result_budget=1_500,
)
START_CALL: Final = ToolSpec(
    name="meetings.start_call",
    toolset=TOOLSET,
    description=(
        "Start a Shosai video call now in a new room of the user's Personal space, after the "
        "user approves. Returns the invite link to share and the room's page to open with "
        "navigate. Leo takes notes of the call unless the user turns them off in the room."
    ),
    input=StartCall,
    output=CallStarted,
    effect=ToolEffect.WRITE,
    reversibility=Reversibility.COMPENSABLE,
    invalidates=MEETINGS_DOMAIN,
    step_detail="title",
    previews=(words.START,),
)
END_CALL: Final = ToolSpec(
    name="meetings.end_call",
    toolset=TOOLSET,
    description=(
        "End one of the user's Shosai calls for everyone, after the user approves: everyone "
        "leaves, the room closes for good and its link stops working."
    ),
    input=EndCall,
    output=CallEnded,
    effect=ToolEffect.WRITE,
    reversibility=Reversibility.IRREVERSIBLE,
    invalidates=MEETINGS_DOMAIN,
    previews=(words.END,),
)
SPECS: Final = (LIST_LIVE, START_CALL, END_CALL)
