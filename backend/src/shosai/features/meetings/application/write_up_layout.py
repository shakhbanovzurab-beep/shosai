"""Which sections a write-up has: a shipped template's, a person's own, or Leo's layout.

A shipped template is known by its code; a person's template by its id, read in their own
scope, since templates are personal. A template whose sections are not ones the template
rules allow is a defect of the stored row and is refused with `ValueError`.
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.meetings.domain.templates import SectionKind, TemplateSection, builtin
from shosai.features.meetings.domain.write_up import SectionPlan, builtin_layout, own_layout
from shosai.features.meetings.infrastructure.notes_records import TemplateRecord


def template_sections(raw: Sequence[dict[str, Any]]) -> list[TemplateSection]:
    """A stored template's sections; `ValueError` when they are not a template's."""
    try:
        sections = [TemplateSection(SectionKind(item["kind"]), item.get("title")) for item in raw]
    except (KeyError, TypeError) as error:
        message = "секции шаблона записаны не по правилам"
        raise ValueError(message) from error
    if not sections:
        message = "у шаблона нет секций"
        raise ValueError(message)
    return sections


async def layout_of(session: AsyncSession, template_id: str) -> tuple[SectionPlan, ...] | None:
    """The template's layout, or None when no such template is visible in the session."""
    shipped = builtin(template_id)
    if shipped is not None:
        return builtin_layout(shipped)
    try:
        own_id = UUID(template_id)
    except ValueError:
        return None
    record = await session.get(TemplateRecord, own_id)
    if record is None:
        return None
    return own_layout(template_sections(record.sections))
