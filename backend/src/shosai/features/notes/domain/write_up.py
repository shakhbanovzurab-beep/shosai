"""Leo's write-up as stored: a template's sections over the findings (plan §3.3, §3.4 flow 6).

A layout is the template's sections in their fixed order, each under a shipped heading's
code or a person's own title. The summary is the only section a model writes; the key
points, decisions and action items list the findings of their kind by id, so a rewrite
with another template keeps every finding and its id. The map is stored as the tree of its
labels. A layout copied into a rewrite's run is read back strictly: anything else is a
defect, never guessed at.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from shosai.features.notes.domain.findings import SECTION_FINDINGS, FindingKind
from shosai.features.notes.domain.mind_map import MapNode
from shosai.features.notes.domain.templates import (
    BuiltinTemplate,
    SectionKind,
    TemplateSection,
)

DOCUMENT_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class SectionPlan:
    """A section to write: its kind and either a shipped heading's code or a person's title."""

    kind: SectionKind
    heading_code: str | None = None
    title: str | None = None

    def __post_init__(self) -> None:
        if (self.heading_code is None) == (self.title is None):
            message = "у секции записи — либо код заголовка, либо своё название"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class ListedFinding:
    """A finding a section may list: its id and kind."""

    finding_id: UUID
    kind: FindingKind


def builtin_layout(template: BuiltinTemplate) -> tuple[SectionPlan, ...]:
    """A shipped template's sections under their headings' codes."""
    return tuple(SectionPlan(s.kind, heading_code=s.heading) for s in template.sections)


def own_layout(sections: Sequence[TemplateSection]) -> tuple[SectionPlan, ...]:
    """A person's template: their titles, or the kind's own heading where they gave none."""
    return tuple(
        SectionPlan(s.kind, title=s.title)
        if s.title is not None
        else SectionPlan(s.kind, heading_code=s.kind.value)
        for s in sections
    )


def _heading(plan: SectionPlan) -> dict[str, str]:
    if plan.title is not None:
        return {"title": plan.title}
    return {"heading_code": plan.heading_code or plan.kind.value}


def layout_json(layout: Sequence[SectionPlan]) -> list[dict[str, str]]:
    """The layout as a rewrite's run keeps it."""
    return [{"kind": plan.kind.value, **_heading(plan)} for plan in layout]


def layout_from_json(raw: Sequence[Mapping[str, Any]]) -> tuple[SectionPlan, ...]:
    """The layout a rewrite's run kept; `ValueError` when it is not one."""
    if not raw:
        message = "в раскладке записи нет секций"
        raise ValueError(message)
    return tuple(
        SectionPlan(SectionKind(item["kind"]), item.get("heading_code"), item.get("title"))
        for item in raw
    )


def written_sections(
    layout: Sequence[SectionPlan], summary: str | None, findings: Sequence[ListedFinding]
) -> list[dict[str, Any]]:
    """The sections as stored: the summary's text, or the ids of the findings of each kind.

    A summary the model did not give is stored as `null`: the page offers a rewrite.
    """
    sections: list[dict[str, Any]] = []
    for plan in layout:
        section: dict[str, Any] = {"kind": plan.kind.value, **_heading(plan)}
        if plan.kind is SectionKind.SUMMARY:
            section["text"] = summary
        else:
            kind = SECTION_FINDINGS[plan.kind]
            section["finding_ids"] = [str(f.finding_id) for f in findings if f.kind is kind]
        sections.append(section)
    return sections


def write_up_document(template_id: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
    """The write-up as `meeting_notes.write_up` keeps it."""
    return {"version": DOCUMENT_VERSION, "template_id": template_id, "sections": sections}


def map_json(node: MapNode) -> dict[str, Any]:
    """The map as `meeting_notes.map` keeps it: labels and children, the root first."""
    return {"label": node.label, "children": [map_json(child) for child in node.children]}
