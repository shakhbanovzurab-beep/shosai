"""The share link's write tools of Leo's `notes` toolset: on with its settings, and off (step 16).

As the other writes (`agent_tool_writes`): `plan` freezes the meeting and the settings,
`preview` tells the card whether the link is new and what its page will show — or how
many comments go with it — and `execute` changes the link through the same service as the
cabinet's route, once per item key, in the meeting's scope. A meeting not kept has no link.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.bindings import WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import (
    PlannedEffect,
    Preview,
    ToolError,
    ToolErrorCode,
    ToolResult,
)
from shosai.core.kernel.errors import AppError
from shosai.features.notes.application.share_links import ShareLinks
from shosai.features.notes.channels.agent_tool_writes import WriteSteps, person, tool_error
from shosai.features.notes.channels.agent_write_tools import (
    REVOKE_SHARE_LINK,
    SET_SHARE_LINK,
    RevokeShareLink,
    SetShareLink,
    ShareLinkRevoked,
    ShareLinkSet,
)
from shosai.features.notes.domain.meetings import PRIVATE_MEETING
from shosai.features.notes.domain.sharing import ShareExpiry, ShareSettings
from shosai.features.notes.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)


def settings_planned(planned: PlannedEffect) -> ShareSettings:
    """The settings the plan froze."""
    data = planned.data
    return ShareSettings(
        show_transcript=bool(data["show_transcript"]), show_names=bool(data["show_names"]),
        allow_comments=bool(data["allow_comments"]), expiry=ShareExpiry(str(data["expiry"])),
    )  # fmt: skip


class LinkWrites:
    """Plans, previews and executes turning a meeting's share link on and off."""

    def __init__(self, steps: WriteSteps, links: ShareLinks) -> None:
        self._steps = steps
        self._links = links

    def bound(
        self,
    ) -> tuple[WriteTool[SetShareLink, ShareLinkSet], WriteTool[RevokeShareLink, ShareLinkRevoked]]:
        """The two write tools."""
        return (
            WriteTool(SET_SHARE_LINK, self.plan_set, self.preview_set, self.execute_set),
            WriteTool(
                REVOKE_SHARE_LINK, self.plan_revoke, self.preview_revoke, self.execute_revoke
            ),
        )

    async def plan_set(
        self, arguments: SetShareLink, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the meeting and the link's settings; a meeting not kept has no link."""
        async with self._steps.transactions.begin(context.scope, read_only=True) as session:
            meeting = await self._steps.managed(session, context, arguments.meeting_id)
        if isinstance(meeting, ToolError):
            return meeting
        if not meeting.kept:
            return ToolError(ToolErrorCode.FAILED, {"reason": PRIVATE_MEETING})
        settings = {
            "show_transcript": arguments.show_transcript, "show_names": arguments.show_names,
            "allow_comments": arguments.allow_comments, "expiry": arguments.expiry.value,
        }  # fmt: skip
        return PlannedEffect((str(meeting.id),), settings)

    async def preview_set(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: which meeting, whether the link is new, and what its page shows."""
        meeting_id = UUID(planned.targets[0])
        link = await self._link(context, meeting_id)
        title = await self._steps.title(context, meeting_id)
        settings = settings_planned(planned)
        params = {
            "title": title, "new": link is None, "show_transcript": settings.show_transcript,
            "show_names": settings.show_names, "allow_comments": settings.allow_comments,
            "expiry": settings.expiry.value,
        }  # fmt: skip
        return Preview("agent.notes.set_share_link", params)

    async def execute_set(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[ShareLinkSet]:
        """Turn the planned meeting's link on with the planned settings only."""
        principal, meeting_id = person(context), UUID(planned.targets[0])
        settings = settings_planned(planned)
        try:
            scope = await self._links.scope_of(principal, meeting_id)
        except AppError as error:
            return ToolResult(error=tool_error(error))

        async def effect(session: AsyncSession) -> ShareLinkSet:
            link = await self._links.put_in(session, principal, meeting_id, settings)
            return ShareLinkSet(
                meeting_id=meeting_id, path=f"/s/{link.token}", expires_at=link.expires_at
            )

        return await self._steps.apply(scope, (key, SET_SHARE_LINK.name), ShareLinkSet, effect)

    async def plan_revoke(
        self, arguments: RevokeShareLink, context: ToolContext
    ) -> PlannedEffect | ToolError:
        """Freeze the meeting whose link goes; a link that is off already is not found."""
        async with self._steps.transactions.begin(context.scope, read_only=True) as session:
            meeting = await self._steps.managed(session, context, arguments.meeting_id)
        if isinstance(meeting, ToolError):
            return meeting
        if await self._link(context, meeting.id) is None:
            return ToolError(ToolErrorCode.NOT_FOUND)
        return PlannedEffect((str(meeting.id),))

    async def preview_revoke(self, planned: PlannedEffect, context: ToolContext) -> Preview:
        """The card: which meeting, and how many comments are deleted with its link."""
        meeting_id = UUID(planned.targets[0])
        comments = 0
        try:
            scope = await self._links.scope_of(person(context), meeting_id)
        except AppError:
            scope = None
        if scope is not None:
            async with self._steps.transactions.begin(scope, read_only=True) as session:
                counted = await session.scalar(
                    select(func.count())
                    .select_from(ShareCommentRecord)
                    .where(ShareCommentRecord.session_id == meeting_id)
                )
                comments = int(counted or 0)
        title = await self._steps.title(context, meeting_id)
        return Preview("agent.notes.revoke_share_link", {"title": title, "comments": comments})

    async def execute_revoke(
        self, planned: PlannedEffect, context: ToolContext, key: str
    ) -> ToolResult[ShareLinkRevoked]:
        """Turn the planned meeting's link off, with its comments."""
        principal, meeting_id = person(context), UUID(planned.targets[0])
        try:
            scope = await self._links.scope_of(principal, meeting_id)
        except AppError as error:
            return ToolResult(error=tool_error(error))

        async def effect(session: AsyncSession) -> ShareLinkRevoked:
            await self._links.remove_in(session, principal, meeting_id)
            return ShareLinkRevoked(meeting_id=meeting_id)

        return await self._steps.apply(
            scope, (key, REVOKE_SHARE_LINK.name), ShareLinkRevoked, effect
        )

    async def _link(self, context: ToolContext, meeting_id: UUID) -> ShareLinkRecord | None:
        """The meeting's link as it is now, read in the meeting's scope; None once it is gone."""
        try:
            scope = await self._links.scope_of(person(context), meeting_id)
        except AppError:
            return None
        async with self._steps.transactions.begin(scope, read_only=True) as session:
            link: ShareLinkRecord | None = await session.get(ShareLinkRecord, meeting_id)
            return link
