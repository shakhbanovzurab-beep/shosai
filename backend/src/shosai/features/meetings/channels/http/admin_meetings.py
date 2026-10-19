"""Support's deleted meetings of a person (`/v1/admin/users/{user_id}/meetings*`, MT-D8).

The admin session gates both routes. The admin names the person and their home (both on
the account's card): the list pages the meetings deleted within the last 7 days, the latest
first, and a restore brings one back, shared nowhere. Both are audited; an account in its
deletion window answers 409 `account_deletion_scheduled` to both. Errors:
`hidden_meeting_not_found`, `invalid_cursor`.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict

from shosai.core.kernel.homes import Home
from shosai.core.pagination.page import Page, PageParameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import require_admin
from shosai.features.meetings.application.support_meetings import SupportMeetings


class HiddenMeetingOut(BaseModel):
    """A deleted meeting support may still restore."""

    id: UUID
    title: str
    started_at: datetime
    seconds: int
    deleted_at: datetime


class MeetingRestoreIn(BaseModel):
    """The person's home, as the account's card shows it."""

    model_config = ConfigDict(extra="forbid")

    home: Home


def build_admin_meetings_router(support: SupportMeetings, ports: PortDirectory) -> APIRouter:
    """Support's routes over deleted meetings."""
    router = APIRouter(
        prefix="/v1/admin/users", tags=["admin"], dependencies=[Depends(require_admin(ports))]
    )

    @router.get("/{user_id}/meetings")
    async def list_hidden_meetings(
        user_id: UUID, home: Annotated[Home, Query()], page: PageParameters
    ) -> Page[HiddenMeetingOut]:
        """The person's meetings deleted within the last 7 days."""
        found = await support.of_person(home, user_id, page)
        return Page(
            items=[
                HiddenMeetingOut(
                    id=m.meeting_id, title=m.title, started_at=m.started_at, seconds=m.seconds,
                    deleted_at=m.deleted_at,
                )
                for m in found.items
            ],
            next_cursor=found.next_cursor,
        )  # fmt: skip

    @router.post("/{user_id}/meetings/{meeting_id}/restore", status_code=HTTPStatus.NO_CONTENT)
    async def restore_meeting(user_id: UUID, meeting_id: UUID, body: MeetingRestoreIn) -> Response:
        """Bring a deleted meeting back, shared nowhere."""
        await support.restore(body.home, user_id, meeting_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
