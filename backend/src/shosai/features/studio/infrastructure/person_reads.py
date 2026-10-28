"""What a resolution reads of a person in the caller's transaction, one statement each.

A model's route reads the role's settings; a prompt reads the role's active prompt with its
skills' ids in order, joined in one statement; the context is one row. Every statement names
the person besides row-level security (ADR 0053).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.studio.domain.roles import PromptRole, RoleSettings
from shosai.features.studio.infrastructure.person_records import (
    ContextRecord,
    PromptRecord,
    PromptSkillRecord,
    RoleModelRecord,
    RolePromptRecord,
)

PROMPT, SKILL, ACTIVE = PromptRecord, PromptSkillRecord, RolePromptRecord


@dataclass(frozen=True, slots=True)
class ActivePrompt:
    """The instructions a role plays by and the ids of the skills they append, in order."""

    content: str
    skill_ids: Sequence[UUID]


async def role_settings(
    session: AsyncSession, user_id: UUID, role: PromptRole
) -> RoleSettings | None:
    """The person's settings of the role; none when they never set it."""
    row = await session.scalar(
        select(RoleModelRecord).where(
            RoleModelRecord.user_id == user_id, RoleModelRecord.role == role.value
        )
    )
    if row is None:
        return None
    return RoleSettings(row.model_id, row.temperature, row.max_tokens, reasoning=row.reasoning)


async def active_prompt(
    session: AsyncSession, user_id: UUID, role: PromptRole
) -> ActivePrompt | None:
    """The role's active prompt with its skills, or none for the built-in prompt."""
    skills = func.array_remove(
        func.array_agg(aggregate_order_by(SKILL.skill_id, SKILL.position)), None
    )
    statement = (
        select(PROMPT.content, skills)
        .join(ACTIVE, and_(ACTIVE.user_id == PROMPT.user_id, ACTIVE.prompt_id == PROMPT.id))
        .outerjoin(SKILL, and_(SKILL.user_id == PROMPT.user_id, SKILL.prompt_id == PROMPT.id))
        .where(ACTIVE.user_id == user_id, ACTIVE.role == role.value)
        .group_by(PROMPT.id)
    )
    row = (await session.execute(statement)).one_or_none()
    if row is None:
        return None
    content, skill_ids = row
    return ActivePrompt(content, tuple(skill_ids or ()))


async def context_of(session: AsyncSession, user_id: UUID) -> str:
    """The person's own words about themselves; empty when they wrote none."""
    content = await session.scalar(
        select(ContextRecord.content).where(ContextRecord.user_id == user_id)
    )
    return content or ""
