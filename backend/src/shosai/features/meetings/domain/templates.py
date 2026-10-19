"""Templates of Leo's write-up (the cabinet's `notes/domain/templates.ts`; plan §3.4).

A template lays the write-up out: which of the four section kinds it has, in their fixed
order, under which headings. Leo's own layout (`enhanced`) has all four. The eight shipped
templates are codes — their names and headings are worded by the cabinet in the interface
language — and are read-only. A person's template has a name of 1 to 60 characters, a
description of at most 120, one of ten icons and one to four sections of distinct kinds,
each with an optional title of at most 40 characters (none: the kind's own heading); a
person keeps at most 50.
"""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

ENHANCED: Final = "enhanced"
NAME_MAX: Final = 60
DESCRIPTION_MAX: Final = 120
SECTION_TITLE_MAX: Final = 40
TEMPLATES_MAX: Final = 50


class SectionKind(StrEnum):
    """What a section of the write-up holds."""

    SUMMARY = "summary"
    KEY_POINTS = "key_points"
    DECISIONS = "decisions"
    ACTION_ITEMS = "action_items"


SECTION_ORDER: Final = tuple(SectionKind)


class TemplateIcon(StrEnum):
    """The icons a template may have."""

    BRIEFCASE = "briefcase"
    CHART = "chart"
    HANDSHAKE = "handshake"
    LANDMARK = "landmark"
    LIGHTBULB = "lightbulb"
    MAGNET = "magnet"
    PHONE = "phone"
    ROCKET = "rocket"
    CALENDAR = "calendar"
    USERS = "users"


@dataclass(frozen=True, slots=True)
class BuiltinSection:
    """A shipped template's section: its kind and its heading's code."""

    kind: SectionKind
    heading: str


@dataclass(frozen=True, slots=True)
class BuiltinTemplate:
    """A template the product ships, by the cabinet's id."""

    template_id: str
    icon: TemplateIcon | None
    sections: tuple[BuiltinSection, ...]


def _shipped(
    template_id: str, icon: TemplateIcon, *sections: tuple[SectionKind, str]
) -> BuiltinTemplate:
    return BuiltinTemplate(template_id, icon, tuple(BuiltinSection(k, h) for k, h in sections))


_S, _K, _D, _A = SectionKind
LEO_LAYOUT: Final = BuiltinTemplate(
    ENHANCED, None, tuple(BuiltinSection(kind, kind.value) for kind in SECTION_ORDER)
)
BUILTIN_TEMPLATES: Final = (
    _shipped("catchUpInvestor", TemplateIcon.HANDSHAKE, (_S, "whereWeAre"), (_K, "updatesShared"),
             (_D, "whatWeAgreed"), (_A, "followUps")),
    _shipped("catchUpPortfolio", TemplateIcon.CHART, (_S, "companyUpdate"),
             (_K, "metricsAndHighlights"), (_A, "howWeCanHelp")),
    _shipped("lpProspective", TemplateIcon.MAGNET, (_S, "overview"), (_K, "theirInterests"),
             (_A, "nextSteps")),
    _shipped("vcBoardMeeting", TemplateIcon.BRIEFCASE, (_S, "boardSummary"), (_K, "discussion"),
             (_D, "resolutions"), (_A, "ownersAndDeadlines")),
    _shipped("vcPitch", TemplateIcon.ROCKET, (_S, "thePitch"), (_K, "whatStoodOut"),
             (_D, "verdict"), (_A, "diligenceToDos")),
    _shipped("oneOnOne", TemplateIcon.USERS, (_S, "howItsGoing"), (_K, "topics"),
             (_A, "nextSteps")),
    _shipped("customerCall", TemplateIcon.PHONE, (_S, "context"), (_K, "painsAndRequests"),
             (_D, "outcome"), (_A, "followUps")),
    _shipped("teamSync", TemplateIcon.CALENDAR, (_K, "updates"), (_D, "decisions"),
             (_A, "whoDoesWhat")),
)  # fmt: skip
BUILTIN_BY_ID: Final = {
    template.template_id: template for template in (LEO_LAYOUT, *BUILTIN_TEMPLATES)
}


class TemplateRule(StrEnum):
    """A rule of a person's templates; the value is the API's error code."""

    NAME_REQUIRED = "template_name_required"
    NAME_TOO_LONG = "template_name_too_long"
    DESCRIPTION_TOO_LONG = "template_description_too_long"
    SECTIONS_REQUIRED = "template_sections_required"
    SECTION_REPEATED = "template_section_repeated"
    SECTION_TITLE_TOO_LONG = "template_section_title_too_long"
    LIMIT_REACHED = "templates_limit_reached"
    BUILTIN_READ_ONLY = "template_builtin_read_only"


class TemplateRuleError(ValueError):
    """A template breaks a rule."""

    def __init__(self, rule: TemplateRule) -> None:
        super().__init__(rule.value)
        self.rule = rule
        self.code = rule.value


@dataclass(frozen=True, slots=True)
class TemplateSection:
    """A section of a person's template; `title` None takes the kind's own heading."""

    kind: SectionKind
    title: str | None = None


@dataclass(frozen=True, slots=True)
class TemplateDraft:
    """A person's template as checked: its name, description, icon and sections in order."""

    name: str
    description: str | None
    icon: TemplateIcon
    sections: tuple[TemplateSection, ...]


def _clean(raw: str) -> str:
    return "".join(char for char in raw if unicodedata.category(char) != "Cc").strip()


def checked_template(
    name: str, description: str | None, icon: TemplateIcon, sections: Sequence[TemplateSection]
) -> TemplateDraft:
    """The template as stored, or the rule it breaks; sections are put in the fixed order."""
    clean_name = _clean(name)
    if not clean_name:
        raise TemplateRuleError(TemplateRule.NAME_REQUIRED)
    if len(clean_name) > NAME_MAX:
        raise TemplateRuleError(TemplateRule.NAME_TOO_LONG)
    clean_description = _clean(description or "") or None
    if clean_description is not None and len(clean_description) > DESCRIPTION_MAX:
        raise TemplateRuleError(TemplateRule.DESCRIPTION_TOO_LONG)
    if not sections:
        raise TemplateRuleError(TemplateRule.SECTIONS_REQUIRED)
    kinds = [section.kind for section in sections]
    if len(set(kinds)) != len(kinds):
        raise TemplateRuleError(TemplateRule.SECTION_REPEATED)
    checked: list[TemplateSection] = []
    for section in sorted(sections, key=lambda s: SECTION_ORDER.index(s.kind)):
        title = _clean(section.title or "") or None
        if title is not None and len(title) > SECTION_TITLE_MAX:
            raise TemplateRuleError(TemplateRule.SECTION_TITLE_TOO_LONG)
        checked.append(TemplateSection(section.kind, title))
    return TemplateDraft(clean_name, clean_description, icon, tuple(checked))


def may_add_template(count: int) -> bool:
    """Whether a person who keeps `count` templates may add one more."""
    return count < TEMPLATES_MAX


def builtin(template_id: str) -> BuiltinTemplate | None:
    """The shipped template or Leo's layout of that id, if it is one."""
    return BUILTIN_BY_ID.get(template_id)
