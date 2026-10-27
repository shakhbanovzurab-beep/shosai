"""A person's prompts, their skills and their personal context (studio plan §2, ADR 0074).

A prompt has a name, a role and instructions, and appends the person's installed skills in
order. A role's prompt and its skills fit 12 000 tokens: a prompt over that is refused when
saved, and a skill that grew after the save is left out in order when the prompt is used.
The personal context is the person's own words about themselves, at most 4 000 characters
(code points, so the cabinet's UTF-16 count is the stricter one), stored trimmed.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.roles import PromptRole

NAME_MAX: Final = 80
CONTENT_MAX: Final = 20_000
SKILLS_MAX: Final = 20
PROMPTS_MAX: Final = 100
CONTEXT_MAX: Final = 4_000
ROLE_PROMPT_TOKENS: Final = 12_000
# Та же оценка, что у сегментов контекста Leo: байты UTF-8 на три, с запасом.
BYTES_PER_TOKEN: Final = 3
# Обёртка навыка у потребителя: границы, метка и имя.
SKILL_WRAP_TOKENS: Final = 24


@dataclass(frozen=True, slots=True)
class PromptDraft:
    """What a person writes in the prompt editor."""

    name: str
    role: PromptRole
    content: str
    skill_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class SkillText:
    """An installed skill a prompt appends: third-party text the consumer wraps."""

    skill_id: UUID
    name: str
    body: str


def estimate_tokens(text: str) -> int:
    """A conservative token count of a text in any language."""
    return math.ceil(len(text.encode()) / BYTES_PER_TOKEN)


def checked_draft(draft: PromptDraft) -> PromptDraft:
    """The draft as it is stored: name and instructions trimmed, each skill once, in order."""
    name, content = draft.name.strip(), draft.content.strip()
    if not name:
        raise StudioRuleError(StudioRule.PROMPT_NAME_REQUIRED)
    if len(name) > NAME_MAX:
        raise StudioRuleError(StudioRule.PROMPT_NAME_TOO_LONG, {"max": NAME_MAX})
    if len(content) > CONTENT_MAX:
        raise StudioRuleError(StudioRule.PROMPT_TOO_LONG, {"max": CONTENT_MAX})
    skills = tuple(dict.fromkeys(draft.skill_ids))
    if len(skills) > SKILLS_MAX:
        raise StudioRuleError(StudioRule.TOO_MANY_SKILLS, {"max": SKILLS_MAX})
    return PromptDraft(name, draft.role, content, skills)


def prompt_tokens(content: str, skills: Sequence[SkillText]) -> int:
    """What a role's prompt and its skills cost in the context."""
    wrapped = sum(estimate_tokens(skill.body) + SKILL_WRAP_TOKENS for skill in skills)
    return estimate_tokens(content) + wrapped


def check_budget(content: str, skills: Sequence[SkillText]) -> None:
    """Refuse a prompt whose instructions and skills do not fit the role's budget."""
    tokens = prompt_tokens(content, skills)
    if tokens > ROLE_PROMPT_TOKENS:
        raise StudioRuleError(
            StudioRule.PROMPT_OVER_BUDGET, {"tokens": tokens, "max": ROLE_PROMPT_TOKENS}
        )


def fitting_skills(
    content: str, skills: Sequence[SkillText]
) -> tuple[tuple[SkillText, ...], tuple[UUID, ...]]:
    """The skills that fit the budget, the first ones in order — order is the person's
    priority — and the ids of the rest, left out."""
    room = ROLE_PROMPT_TOKENS - estimate_tokens(content)
    for index, skill in enumerate(skills):
        cost = estimate_tokens(skill.body) + SKILL_WRAP_TOKENS
        if cost > room:
            return tuple(skills[:index]), tuple(rest.skill_id for rest in skills[index:])
        room -= cost
    return tuple(skills), ()


def checked_context(content: str) -> str:
    """The personal context as it is stored: trimmed, within its length."""
    trimmed = content.strip()
    if len(trimmed) > CONTEXT_MAX:
        raise StudioRuleError(StudioRule.CONTEXT_TOO_LONG, {"max": CONTEXT_MAX})
    return trimmed
