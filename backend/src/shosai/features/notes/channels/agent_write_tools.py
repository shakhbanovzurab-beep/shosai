"""The write tools of Leo's `notes` toolset: a folder, a new write-up, the share link (step 16).

Each changes one meeting the user may manage, and only after the user approves the card
the server writes for it (Leo §8.1, §8.4): filing one of their own meetings in one of their
folders (by the folder's name, since no tool lists folder ids), rewriting Leo's notes by a
shipped template, turning the meeting's share link on with its settings, or off. Results
carry ids and the user's own settings only, so they have no provenance label.
"""

from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from pydantic import BaseModel, Field

from shosai.core.agent_tools.spec import CostClass, Reversibility, ToolEffect, ToolSpec
from shosai.features.notes.channels import agent_previews as words
from shosai.features.notes.channels.agent_tools import Strict
from shosai.features.notes.domain.sharing import ShareExpiry

NOTES_DOMAIN: Final = ("notes",)
FOLDER_NAME_MAX: Final = 200


class TemplateCode(StrEnum):
    """A shipped template of Leo's write-up, by its code."""

    ENHANCED = "enhanced"
    CATCH_UP_INVESTOR = "catchUpInvestor"
    CATCH_UP_PORTFOLIO = "catchUpPortfolio"
    LP_PROSPECTIVE = "lpProspective"
    VC_BOARD_MEETING = "vcBoardMeeting"
    VC_PITCH = "vcPitch"
    ONE_ON_ONE = "oneOnOne"
    CUSTOMER_CALL = "customerCall"
    TEAM_SYNC = "teamSync"


class MoveToFolder(Strict):
    """Arguments of filing a meeting."""

    meeting_id: UUID = Field(description="The id of one of the user's own meetings.")
    folder: str | None = Field(
        min_length=1, max_length=FOLDER_NAME_MAX,
        description="The name of one of the user's folders; null takes the meeting out of its "
        "folder.",
    )  # fmt: skip


class MovedToFolder(BaseModel):
    """Where the meeting is filed now."""

    meeting_id: UUID = Field(description="The meeting's id.")
    folder: str | None = Field(description="The folder's name; null when it is in no folder.")


class RegenerateNotes(Strict):
    """Arguments of a new write-up."""

    meeting_id: UUID = Field(description="The id of a meeting whose notes are written.")
    template: TemplateCode | None = Field(
        default=None,
        description="The shipped template to follow: enhanced is Leo's summary, key points, "
        "decisions and action items; the others are named for the kind of meeting. Leave out "
        "to keep the meeting's own template.",
    )


class NotesRegenerating(BaseModel):
    """The rewrite that started."""

    meeting_id: UUID = Field(description="The meeting's id.")
    run_id: UUID = Field(description="The run writing the new notes; they appear in minutes.")


class SetShareLink(Strict):
    """Arguments of the meeting's share link."""

    meeting_id: UUID = Field(description="The id of a meeting the user may manage.")
    show_transcript: bool = Field(
        default=True, description="Whether the page shows the transcript."
    )
    show_names: bool = Field(
        default=False, description="Whether the page shows people's names; numbers otherwise."
    )
    allow_comments: bool = Field(default=False, description="Whether visitors may comment.")
    expiry: ShareExpiry = Field(
        default=ShareExpiry.NEVER, description="How long the link works: never, 7d, 30d or 90d."
    )


class ShareLinkSet(BaseModel):
    """The link as it is now."""

    meeting_id: UUID = Field(description="The meeting's id.")
    path: str = Field(description="The link's path on Shosai's site, to give to the user.")
    expires_at: datetime | None = Field(description="When it stops working, in UTC; null never.")


class RevokeShareLink(Strict):
    """Arguments of turning the link off."""

    meeting_id: UUID = Field(description="The id of a meeting whose link is on.")


class ShareLinkRevoked(BaseModel):
    """The link is off."""

    meeting_id: UUID = Field(description="The meeting's id; its link and comments are gone.")


MOVE_TO_FOLDER: Final = ToolSpec(
    name="notes.move_to_folder",
    toolset="notes",
    description=(
        "File one of the user's own meetings in one of their folders, named as the user calls "
        "it, or take it out of its folder. The user approves the move first."
    ),
    input=MoveToFolder, output=MovedToFolder, effect=ToolEffect.WRITE,
    reversibility=Reversibility.REVERSIBLE, result_budget=300, invalidates=NOTES_DOMAIN,
    previews=(words.MOVE_TO_FOLDER, words.REMOVE_FROM_FOLDER),
)  # fmt: skip
REGENERATE_NOTES: Final = ToolSpec(
    name="notes.regenerate_notes",
    toolset="notes",
    description=(
        "Write a meeting's notes again by a template: a new summary and sections over the same "
        "findings. The current write-up is replaced and cannot be brought back; the user's own "
        "notes are never touched. The user approves it first."
    ),
    input=RegenerateNotes, output=NotesRegenerating, effect=ToolEffect.WRITE,
    reversibility=Reversibility.IRREVERSIBLE, cost_class=CostClass.METERED, result_budget=300,
    invalidates=NOTES_DOMAIN,
    previews=(words.REGENERATE_NOTES,),
)  # fmt: skip
SET_SHARE_LINK: Final = ToolSpec(
    name="notes.set_share_link",
    toolset="notes",
    description=(
        "Turn on a meeting's public link, or change what its page shows: anyone with the link "
        "can open the write-up, and the transcript and names if allowed. Changing the settings "
        "keeps the link. The user approves it first."
    ),
    input=SetShareLink, output=ShareLinkSet, effect=ToolEffect.WRITE,
    reversibility=Reversibility.COMPENSABLE, result_budget=300, invalidates=NOTES_DOMAIN,
    previews=(words.SET_SHARE_LINK,),
)  # fmt: skip
REVOKE_SHARE_LINK: Final = ToolSpec(
    name="notes.revoke_share_link",
    toolset="notes",
    description=(
        "Turn a meeting's public link off: it stops opening at once and its comments are "
        "deleted; a link turned on later is a new one. The user approves it first."
    ),
    input=RevokeShareLink, output=ShareLinkRevoked, effect=ToolEffect.WRITE,
    reversibility=Reversibility.IRREVERSIBLE, result_budget=300, invalidates=NOTES_DOMAIN,
    previews=(words.REVOKE_SHARE_LINK,),
)  # fmt: skip
WRITE_TOOLS: Final = (MOVE_TO_FOLDER, REGENERATE_NOTES, SET_SHARE_LINK, REVOKE_SHARE_LINK)
