"""A person's meetings setting: `GET` and `PUT /v1/meetings/settings` (plan step 12, MT-D6).

`keep_meetings` false is "Don't keep my meetings": the meetings the person starts from then
on are shown live and not stored; their minutes still count. The privacy settings show it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.meeting_settings import MeetingSettings


class MeetingSettingsOut(BaseModel):
    """Whether the person's meetings are kept."""

    keep_meetings: bool


class MeetingSettingsIn(BaseModel):
    """Whether to keep the meetings the person starts from now."""

    model_config = ConfigDict(extra="forbid")

    keep_meetings: bool


def build_settings_router(settings: MeetingSettings, ports: PortDirectory) -> APIRouter:
    """The person's meetings setting."""
    router = APIRouter(prefix="/v1/meetings/settings", tags=["meetings"])
    signed_in = bearer_principal(ports)

    @router.get("")
    async def get_meeting_settings(
        principal: Annotated[Principal, Depends(signed_in)],
    ) -> MeetingSettingsOut:
        """Whether your meetings are kept."""
        return MeetingSettingsOut(keep_meetings=await settings.keeps_meetings(principal))

    @router.put("")
    async def put_meeting_settings(
        principal: Annotated[Principal, Depends(signed_in)], body: MeetingSettingsIn
    ) -> MeetingSettingsOut:
        """Keep, or stop keeping, the meetings you start from now."""
        kept = await settings.keep_meetings(principal, keep=body.keep_meetings)
        return MeetingSettingsOut(keep_meetings=kept)

    return router
