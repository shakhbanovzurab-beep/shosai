"""The person's installed skills for studio's prompts (`SkillReader`, ADR 0068 AG-D11).

Studio composes a prompt with the skills it names; it asks for them by id in the person's
transaction and gets those the person installed, each with its body and the commit it is
pinned to. An id the person does not have — removed since, or someone else's — is absent.
"""

from collections.abc import Collection, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.agent.contracts import InstalledSkill
from shosai.features.agent.infrastructure.person_records import AgentSkillRecord

SKILL = AgentSkillRecord


class InstalledSkills:
    """Reads the person's skills by id."""

    async def skills(
        self, session: AsyncSession, user_id: UUID, ids: Collection[UUID]
    ) -> Mapping[UUID, InstalledSkill]:
        """The skills among `ids` the person installed; others are absent."""
        if not ids:
            return {}
        found = await session.scalars(
            select(SKILL).where(SKILL.user_id == user_id, SKILL.id.in_(list(ids)))
        )
        return {
            row.id: InstalledSkill(
                id=row.id, name=row.slug, description=row.description, body=row.body,
                repository=row.repo, path=row.skill_path, commit=row.ref,
            )
            for row in found
        }  # fmt: skip
