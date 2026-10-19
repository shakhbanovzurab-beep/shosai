"""The shapes of the person's notes, participants, folders and templates (plan step 7b).

They follow the cabinet's `ManualNotes`, `NoteParticipant`, `NoteFolder` and `NoteTemplate`
(`frontend/src/features/notes/domain`), named for the API in snake_case. A shipped
template carries codes the cabinet words in the interface language, never words.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shosai.features.meetings.application.folders import Folder
from shosai.features.meetings.application.my_notes import OwnNotes
from shosai.features.meetings.application.templates import SectionRequest, Template
from shosai.features.meetings.domain.library import FolderColor, NoteClient
from shosai.features.meetings.domain.templates import SectionKind, TemplateIcon


class OwnNotesOut(BaseModel):
    """What the person typed about the meeting, and where they last wrote it."""

    text: str = Field(description="Markdown.")
    version: int = Field(description="Grows by one with every write, from any client.")
    client: NoteClient
    updated_at: datetime


class MyNotesOut(BaseModel):
    """The person's own notes; null before they have written any."""

    notes: OwnNotesOut | None


class MyNotesIn(BaseModel):
    """The notes' new text; it replaces the old one."""

    model_config = ConfigDict(extra="forbid")

    # Граница — потолок нативного маршрута; 50 000 символов кабинета проверяет домен.
    text: Annotated[str, Field(max_length=262_144, description="Markdown, at most 50 000.")]


class ParticipantIn(BaseModel):
    """A participant to add by address."""

    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(min_length=3, max_length=254)]
    name: Annotated[str | None, Field(max_length=200)] = None


class FolderOut(BaseModel):
    """A folder of the person's."""

    id: UUID
    name: str
    color: FolderColor
    created_at: datetime


class FolderIn(BaseModel):
    """A folder's name."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=200)]


class TemplateSectionOut(BaseModel):
    """A section of a template: a shipped heading's code, or the person's own title."""

    kind: SectionKind
    heading_code: str | None
    title: str | None


class TemplateOut(BaseModel):
    """A template of Leo's write-up; a shipped one has no words of its own."""

    id: str
    builtin: bool
    name: str | None
    description: str | None
    icon: str = Field(description="One of the ten icons, or `enhanced` for Leo's layout.")
    sections: list[TemplateSectionOut]


class TemplatesOut(BaseModel):
    """Every template the person may use: one page, 9 shipped and at most 50 of their own."""

    items: list[TemplateOut]
    next_cursor: None = None


class TemplateSectionIn(BaseModel):
    """A section of a person's template."""

    model_config = ConfigDict(extra="forbid")

    kind: SectionKind
    title: Annotated[str | None, Field(max_length=200)] = None


class TemplateIn(BaseModel):
    """A person's template: its name, description, icon and sections."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(max_length=200)]
    description: Annotated[str | None, Field(max_length=500)] = None
    icon: TemplateIcon
    sections: Annotated[list[TemplateSectionIn], Field(max_length=8)]

    def request(self) -> list[SectionRequest]:
        """The sections as the service takes them."""
        return [SectionRequest(kind=s.kind, title=s.title) for s in self.sections]


def notes_out(notes: OwnNotes | None) -> MyNotesOut:
    """The person's notes, or null."""
    if notes is None:
        return MyNotesOut(notes=None)
    return MyNotesOut(
        notes=OwnNotesOut(
            text=notes.text, version=notes.version, client=notes.client,
            updated_at=notes.updated_at,
        )
    )  # fmt: skip


def folder_out(folder: Folder) -> FolderOut:
    """A folder."""
    return FolderOut(
        id=folder.folder_id, name=folder.name, color=folder.color, created_at=folder.created_at
    )


def template_out(template: Template) -> TemplateOut:
    """A template."""
    return TemplateOut(
        id=template.template_id, builtin=template.builtin, name=template.name,
        description=template.description, icon=template.icon,
        sections=[
            TemplateSectionOut(kind=s.kind, heading_code=s.heading_code, title=s.title)
            for s in template.sections
        ],
    )  # fmt: skip
