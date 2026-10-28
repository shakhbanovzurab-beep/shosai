"""A person's prompts as studio reads and writes them in the person's transaction.

Every statement names the person besides row-level security (ADR 0053): a row of someone
else is not found, whatever the policy. A prompt's skills are its rows in `prompt_skills`
by position; writing them replaces them whole. Creating a prompt counts the person's
prompts under their lock, so two creates at once cannot pass the limit together.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.ids import new_id
from shosai.features.studio.domain.roles import PromptRole
from shosai.features.studio.infrastructure.person_records import (
    PromptRecord,
    PromptSkillRecord,
    RolePromptRecord,
)

PROMPT = PromptRecord
SKILL = PromptSkillRecord
ACTIVE = RolePromptRecord
# Пространство ключей блокировок промтов (ASCII «Stp»); второй ключ — id человека в 32 битах.
PROMPTS_LOCK_SPACE: Final = 0x537470
WORD: Final = 2**32


@dataclass(frozen=True, slots=True)
class StoredPrompt:
    """A person's prompt with its skills in order."""

    id: UUID
    name: str
    role: PromptRole
    content: str
    skill_ids: tuple[UUID, ...]
    updated_at: datetime


def person_key(user_id: UUID) -> int:
    """The person's half of the lock's key: the id folded into a signed 32-bit integer."""
    folded = user_id.int
    folded ^= folded >> 64
    folded ^= folded >> 32
    folded %= WORD
    return folded - WORD if folded >= WORD // 2 else folded


async def hold_prompts_lock(session: AsyncSession, user_id: UUID) -> None:
    """Wait for and hold the person's prompts lock until the transaction ends."""
    await session.execute(
        select(func.pg_advisory_xact_lock(PROMPTS_LOCK_SPACE, person_key(user_id)))
    )


async def prompts_count(session: AsyncSession, user_id: UUID) -> int:
    """How many prompts the person has."""
    return await session.scalar(select(func.count()).where(PROMPT.user_id == user_id)) or 0


async def skills_of(
    session: AsyncSession, user_id: UUID, prompt_ids: Sequence[UUID]
) -> Mapping[UUID, tuple[UUID, ...]]:
    """Each prompt's skills in order."""
    if not prompt_ids:
        return {}
    rows = await session.execute(
        select(SKILL.prompt_id, SKILL.skill_id)
        .where(SKILL.user_id == user_id, SKILL.prompt_id.in_(prompt_ids))
        .order_by(SKILL.prompt_id, SKILL.position)
    )
    found: dict[UUID, list[UUID]] = {}
    for prompt_id, skill_id in rows:
        found.setdefault(prompt_id, []).append(skill_id)
    return {prompt_id: tuple(skills) for prompt_id, skills in found.items()}


def stored(record: PromptRecord, skills: Sequence[UUID]) -> StoredPrompt:
    """The read model of a row and its skills."""
    return StoredPrompt(
        id=record.id,
        name=record.name,
        role=PromptRole(record.role),
        content=record.content,
        skill_ids=tuple(skills),
        updated_at=record.updated_at,
    )


async def prompts_of(session: AsyncSession, user_id: UUID) -> tuple[StoredPrompt, ...]:
    """The person's prompts, the last changed first."""
    records = (
        await session.scalars(
            select(PROMPT)
            .where(PROMPT.user_id == user_id)
            .order_by(PROMPT.updated_at.desc(), PROMPT.id)
        )
    ).all()
    skills = await skills_of(session, user_id, [record.id for record in records])
    return tuple(stored(record, skills.get(record.id, ())) for record in records)


async def prompt_record(
    session: AsyncSession, user_id: UUID, prompt_id: UUID, *, lock: bool = False
) -> PromptRecord | None:
    """The person's prompt row, locked for an update when asked."""
    statement = select(PROMPT).where(PROMPT.id == prompt_id, PROMPT.user_id == user_id)
    return await session.scalar(statement.with_for_update() if lock else statement)


async def prompt_of(session: AsyncSession, user_id: UUID, prompt_id: UUID) -> StoredPrompt | None:
    """The person's prompt with its skills."""
    record = await prompt_record(session, user_id, prompt_id)
    if record is None:
        return None
    skills = await skills_of(session, user_id, [prompt_id])
    return stored(record, skills.get(prompt_id, ()))


async def active_of(session: AsyncSession, user_id: UUID) -> Mapping[PromptRole, UUID | None]:
    """The prompt each of the five roles plays by; none is the built-in prompt."""
    rows = await session.execute(
        select(ACTIVE.role, ACTIVE.prompt_id).where(ACTIVE.user_id == user_id)
    )
    chosen = {PromptRole(role): prompt_id for role, prompt_id in rows}
    return {role: chosen.get(role) for role in PromptRole}


async def write_skills(
    session: AsyncSession, user_id: UUID, prompt_id: UUID, skill_ids: Sequence[UUID]
) -> None:
    """Replace the prompt's skills by these, in order."""
    await session.execute(
        delete(SKILL).where(SKILL.user_id == user_id, SKILL.prompt_id == prompt_id)
    )
    if skill_ids:
        await session.execute(
            insert(SKILL),
            [
                {
                    "id": new_id(),
                    "user_id": user_id,
                    "prompt_id": prompt_id,
                    "skill_id": skill_id,
                    "position": position,
                }
                for position, skill_id in enumerate(skill_ids)
            ],
        )


async def release_roles(session: AsyncSession, user_id: UUID, prompt_id: UUID) -> None:
    """The roles the prompt served go back to their built-in prompts."""
    await session.execute(
        delete(ACTIVE).where(ACTIVE.user_id == user_id, ACTIVE.prompt_id == prompt_id)
    )


async def choose(session: AsyncSession, user_id: UUID, role: PromptRole, prompt_id: UUID) -> None:
    """The role plays by the prompt from now on."""
    statement = insert(ACTIVE).values(
        user_id=user_id, role=role.value, prompt_id=prompt_id, updated_at=func.now()
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[ACTIVE.user_id, ACTIVE.role],
            set_={"prompt_id": prompt_id, "updated_at": func.now()},
        )
    )


async def unchoose(session: AsyncSession, user_id: UUID, role: PromptRole) -> None:
    """The role plays by its built-in prompt from now on."""
    await session.execute(
        delete(ACTIVE).where(ACTIVE.user_id == user_id, ACTIVE.role == role.value)
    )


async def detach_skill(session: AsyncSession, user_id: UUID, skill_id: UUID) -> int:
    """Take an uninstalled skill off every prompt of the person; how many it was on."""
    # Через соединение: оператор ядра отдаёт число удалённых строк без RETURNING.
    connection = await session.connection()
    result = await connection.execute(
        delete(SKILL).where(SKILL.user_id == user_id, SKILL.skill_id == skill_id)
    )
    return result.rowcount
