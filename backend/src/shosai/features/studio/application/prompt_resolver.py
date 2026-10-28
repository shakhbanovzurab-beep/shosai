"""The platform's and a person's prompts for their consumers (`PROMPT_RESOLVER`, plan §3.4).

The platform layer and the features' addenda come from the process's snapshot. A person's
role prompt is one statement in the caller's transaction — the active prompt with its skills'
ids in order — and the skills' bodies are agent's, read through `SkillReader` in the same
transaction: a skill uninstalled since is absent. The skills that fit the role's budget are
kept in the person's order, the rest left out and counted. The personal context is one row.
"""

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.contracts import SKILL_READER
from shosai.features.studio.application.platform_reader import PlatformPromptReader
from shosai.features.studio.contracts import PlatformLayer, RolePrompt
from shosai.features.studio.domain.platform_layer import PlatformFeature
from shosai.features.studio.domain.prompts import SkillText, fitting_skills
from shosai.features.studio.domain.roles import PromptRole
from shosai.features.studio.infrastructure.person_reads import active_prompt, context_of
from shosai.features.studio.infrastructure.route_metrics import RouteMetrics

log = structlog.stdlib.get_logger(__name__)


class StudioPromptResolver:
    """The `PROMPT_RESOLVER` binding: the platform's layer and the person's own prompts."""

    def __init__(
        self, platform: PlatformPromptReader, ports: PortDirectory, metrics: RouteMetrics
    ) -> None:
        self._platform = platform
        self._ports = ports
        self._metrics = metrics

    async def platform_layer(self) -> PlatformLayer:
        """The published layer, read from the process's snapshot."""
        return await self._platform.platform_layer()

    async def feature_prompt(self, feature: PlatformFeature) -> str:
        """The operator's addendum to a feature's prompt; empty when it is off."""
        return await self._platform.feature_prompt(feature)

    async def role_prompt(
        self, session: AsyncSession, user_id: UUID, role: PromptRole
    ) -> RolePrompt:
        """The person's active prompt for the role with its skills, within the budget."""
        found = await active_prompt(session, user_id, role)
        if found is None:
            return RolePrompt(None)
        installed = await self._ports.get(SKILL_READER).skills(session, user_id, found.skill_ids)
        skills = [
            SkillText(skill_id, installed[skill_id].name, installed[skill_id].body)
            for skill_id in found.skill_ids
            if skill_id in installed
        ]
        kept, left = fitting_skills(found.content, skills)
        if left:
            self._metrics.skills_left_out(len(left))
            log.info("Навыки не вошли в бюджет промта", role=role.value, left=len(left))
        return RolePrompt(found.content, kept)

    async def personal_context(self, session: AsyncSession, user_id: UUID) -> str:
        """The person's own words about themselves; empty when they wrote none."""
        return await context_of(session, user_id)
