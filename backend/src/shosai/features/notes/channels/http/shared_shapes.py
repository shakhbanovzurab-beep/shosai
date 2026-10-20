"""What a share link's page and its keeper see, redacted by the link (step 13, MT-D5).

The page never shows an address. With names hidden it gives only how many people took
part, no owner of an action item and no name of a voice; voices are numbered by first
appearance either way, and the reader's interface words the number ("Speaker 2"). With
names shown, the owner's own voice carries the owner's name — the one name a voice has
until commitments knows people. Headings come as the write-up keeps them, codes the
reader's interface words. The transcript is there only when the link shows it.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from shosai.features.notes.application.shared_pages import SharedPage
from shosai.features.notes.domain.findings import FindingKind
from shosai.features.notes.domain.redaction import owner_view, people_view, speaker_views
from shosai.features.notes.domain.sharing import ShareExpiry
from shosai.features.notes.domain.templates import SectionKind
from shosai.features.notes.domain.transcript import SIDE_SPEAKER, Side
from shosai.features.notes.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)


class ShareLinkOut(BaseModel):
    """The meeting's link and what its page shows."""

    token: str
    path: str = Field(description="The page's path on the site, `/s/{token}`.")
    show_transcript: bool
    show_names: bool
    allow_comments: bool
    expiry: ShareExpiry
    expires_at: datetime | None = Field(description="When the link stops working; null never.")


class ShareLinkAnswer(BaseModel):
    """The meeting's link, null while it is off."""

    link: ShareLinkOut | None


class SharedItemOut(BaseModel):
    """A finding the write-up lists, as the page shows it."""

    id: UUID
    kind: FindingKind
    text: str
    owner_name: str | None = Field(description="Shown only when the link shows names.")
    due_on: date | None


class SharedSectionOut(BaseModel):
    """A section of the write-up: a summary's text, or the findings it lists."""

    kind: SectionKind
    heading_code: str | None = Field(
        description="A shipped heading, worded by the reader's interface."
    )
    title: str | None = Field(description="The meeting owner's own title of the section.")
    text: str | None = None
    items: list[SharedItemOut] | None = None


class SharedLineOut(BaseModel):
    """A transcript line on the page."""

    start_ms: int
    duration_ms: int
    speaker: int | None = Field(description="The voice's number by first appearance, from 1.")
    speaker_name: str | None = Field(description="The owner's name for their voice, names shown.")
    text: str


class SharedMeetingOut(BaseModel):
    """A meeting as people outside it see it through the link."""

    title: str
    started_at: datetime
    seconds: int
    participants: list[str] | None = Field(description="Names; null when the link hides them.")
    participant_count: int
    sections: list[SharedSectionOut]
    transcript: list[SharedLineOut] | None = Field(description="Null when the link hides it.")
    transcript_truncated: bool = Field(
        description="Whether lines past the first 3 000 are left out."
    )
    allow_comments: bool


class SharedCommentIn(BaseModel):
    """A reader's comment: a name of at most 60 characters, or none for a guest."""

    author: str | None = Field(default=None, max_length=200)
    text: str = Field(max_length=10_000)


class SharedCommentOut(BaseModel):
    """A comment under the page."""

    id: UUID
    author: str | None = Field(description="Null for a guest.")
    text: str
    created_at: datetime


class SharedCommentsOut(BaseModel):
    """The newest comments, oldest first."""

    items: list[SharedCommentOut]


def link_out(link: ShareLinkRecord | None) -> ShareLinkAnswer:
    """The keeper's view of the link."""
    if link is None:
        return ShareLinkAnswer(link=None)
    return ShareLinkAnswer(
        link=ShareLinkOut(
            token=link.token, path=f"/s/{link.token}", show_transcript=link.show_transcript,
            show_names=link.show_names, allow_comments=link.allow_comments,
            expiry=ShareExpiry(link.expiry), expires_at=link.expires_at,
        )
    )  # fmt: skip


def comment_out(comment: ShareCommentRecord) -> SharedCommentOut:
    """A comment under the page."""
    return SharedCommentOut(
        id=comment.id, author=comment.author, text=comment.text, created_at=comment.created_at
    )


def sections_out(page: SharedPage) -> list[SharedSectionOut]:
    """The write-up's sections with the findings they list, owners only with names shown."""
    if page.notes is None or page.notes.write_up is None:
        return []
    names = page.link.show_names
    out: list[SharedSectionOut] = []
    for section in page.notes.write_up.get("sections", []):
        items = None
        if "finding_ids" in section:
            listed = ((UUID(raw), page.findings.get(UUID(raw))) for raw in section["finding_ids"])
            items = [
                SharedItemOut(
                    id=finding_id, kind=finding.kind, text=finding.text,
                    owner_name=owner_view(finding.owner_name, show_names=names),
                    due_on=finding.due_on,
                )
                for finding_id, finding in listed
                if finding is not None
            ]  # fmt: skip
        out.append(
            SharedSectionOut(
                kind=SectionKind(section["kind"]), heading_code=section.get("heading_code"),
                title=section.get("title"), text=section.get("text"), items=items,
            )
        )  # fmt: skip
    return out


def transcript_out(page: SharedPage) -> list[SharedLineOut] | None:
    """The lines with their voices numbered, the owner's named when names show."""
    if page.lines is None:
        return None
    voices = speaker_views([line.speaker_idx for line in page.lines], {}, show_names=False)
    owner = next((idx for idx, role in page.roles.items() if role == "owner"), None)
    if owner is None and not page.roles:
        owner = SIDE_SPEAKER[Side.ME]
    name = page.owner_name if page.link.show_names else None
    return [
        SharedLineOut(
            start_ms=line.start_ms, duration_ms=line.duration_ms,
            speaker=voices[line.speaker_idx].number if line.speaker_idx is not None else None,
            speaker_name=name if line.speaker_idx == owner else None, text=line.text,
        )
        for line in page.lines
    ]  # fmt: skip


def page_out(page: SharedPage) -> SharedMeetingOut:
    """The link's page, redacted by the link."""
    people = people_view(page.participants, show_names=page.link.show_names)
    meeting = page.meeting
    return SharedMeetingOut(
        title=meeting.title, started_at=meeting.started_at, seconds=meeting.seconds,
        participants=None if people.names is None else list(people.names),
        participant_count=people.count, sections=sections_out(page),
        transcript=transcript_out(page), transcript_truncated=page.truncated,
        allow_comments=page.link.allow_comments,
    )  # fmt: skip
