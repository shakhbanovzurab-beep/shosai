"""A meeting's content: its transcript, write-up, findings and map (plan step 7a, §10).

- `GET /v1/meetings/{id}/transcript` pages the lines in the order they were spoken, up to
  500 a page.
- `…/write-up` is Leo's write-up with the findings each section lists.
- `…/findings` pages the findings the notes list, optionally of one kind.
- `…/map` pages the mind map's nodes in pre-order.

Errors: `meeting_not_found`, `write_up_not_found`, `map_not_found`, `invalid_cursor`.
"""

from typing import Annotated, Any, Final
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from shosai.core.pagination.page import Page, PageParameters, PageRequest, page_parameters
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.meetings.application.meeting_content import MeetingContent, WriteUp
from shosai.features.meetings.channels.http.meeting_models import (
    FindingOut,
    MapNodeOut,
    SectionOut,
    TranscriptLineOut,
    WriteUpOut,
    finding_out,
    line_out,
    node_out,
)
from shosai.features.meetings.domain.findings import FindingKind
from shosai.features.meetings.domain.templates import SectionKind

TRANSCRIPT_PAGE_MAX: Final = 500
TRANSCRIPT_PAGE_DEFAULT: Final = 200
TranscriptPage = Annotated[
    PageRequest, Depends(page_parameters(TRANSCRIPT_PAGE_DEFAULT, TRANSCRIPT_PAGE_MAX))
]


def section_out(section: dict[str, Any], write_up: WriteUp) -> SectionOut:
    """A stored section with the findings it lists, in its order; a gone finding is skipped."""
    kind = SectionKind(section["kind"])
    items = None
    if kind is not SectionKind.SUMMARY:
        listed = (write_up.findings.get(UUID(i)) for i in section.get("finding_ids", []))
        items = [finding_out(finding) for finding in listed if finding is not None]
    return SectionOut(
        kind=kind,
        heading_code=section.get("heading_code"),
        title=section.get("title"),
        text=section.get("text") if kind is SectionKind.SUMMARY else None,
        items=items,
    )


def build_meeting_content_router(content: MeetingContent, ports: PortDirectory) -> APIRouter:
    """The transcript, write-up, findings and map of a meeting."""
    router = APIRouter(prefix="/v1/meetings", tags=["meetings"])
    signed_in = bearer_principal(ports)

    @router.get("/{meeting_id}/transcript")
    async def get_transcript(
        principal: Annotated[Principal, Depends(signed_in)],
        meeting_id: UUID,
        page: TranscriptPage,
    ) -> Page[TranscriptLineOut]:
        """A page of the meeting's lines in the order they were spoken."""
        lines = await content.transcript(principal, meeting_id, page)
        return Page(items=[line_out(line) for line in lines.items], next_cursor=lines.next_cursor)

    @router.get("/{meeting_id}/write-up")
    async def get_write_up(
        principal: Annotated[Principal, Depends(signed_in)], meeting_id: UUID
    ) -> WriteUpOut:
        """Leo's write-up of the meeting by its template."""
        write_up = await content.write_up(principal, meeting_id)
        return WriteUpOut(
            template_id=write_up.template_id,
            automatic=write_up.automatic,
            written_at=write_up.written_at,
            revision=write_up.revision,
            sections=[section_out(section, write_up) for section in write_up.sections],
        )

    @router.get("/{meeting_id}/findings")
    async def list_findings(
        principal: Annotated[Principal, Depends(signed_in)],
        meeting_id: UUID,
        page: PageParameters,
        kind: Annotated[
            FindingKind | None, Query(description="Only findings of this kind.")
        ] = None,
    ) -> Page[FindingOut]:
        """A page of the meeting's findings, in the order they came up."""
        found = await content.findings(principal, meeting_id, page, kind)
        return Page(items=[finding_out(f) for f in found.items], next_cursor=found.next_cursor)

    @router.get("/{meeting_id}/map")
    async def get_map(
        principal: Annotated[Principal, Depends(signed_in)], meeting_id: UUID, page: PageParameters
    ) -> Page[MapNodeOut]:
        """A page of the mind map's nodes, the root first."""
        nodes = await content.map(principal, meeting_id, page)
        return Page(items=[node_out(row) for row in nodes.items], next_cursor=nodes.next_cursor)

    return router
