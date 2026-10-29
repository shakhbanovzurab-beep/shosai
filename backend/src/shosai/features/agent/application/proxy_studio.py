"""What studio adds to a desktop answer (studio plan §3.4, step 11b).

A desktop answer's system messages, in order: the role's frame — the language rule — with the
operator's platform layer after it, then the person's own words about themselves when they send
them to the role (ST-D2 as amended), then the
person's prompt for the role or the built-in one, with the skills it appends, each wrapped as
`skill:user` and placed under a line that keeps the rules above higher (Leo §8.5). The client's
conversation follows. The proxy's roles are Studio's: `responses` answers as `live_answers`,
`coding` as `code`, `system_design` as itself and the screenshots as `screenshots`.
"""

import secrets
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.agent_tools.provenance import Provenance
from shosai.core.ai.requests import ChatMessage, Role
from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.proxy_requests import said
from shosai.features.agent.domain.wrapper import BOUNDARY_BYTES, Label, boundary, wrap
from shosai.features.agent.infrastructure.prompts import (
    PERSONAL_CONTEXT,
    PROXY_CODE,
    PROXY_RESPONSES,
    PROXY_SKILLS,
    PROXY_SYSTEM_DESIGN,
    SKILL_HEADING,
)
from shosai.features.studio.contracts import PROMPT_RESOLVER, PromptRole, RolePrompt

# Роль прокси у клиента — роль Studio и её встроенный промт (у скриншотов он в рамке).
PROXY_ROLES: Final = {
    "responses": PromptRole.LIVE_ANSWERS,
    "coding": PromptRole.CODE,
    "system_design": PromptRole.SYSTEM_DESIGN,
}
BUILT_IN: Final = {
    PromptRole.LIVE_ANSWERS: PROXY_RESPONSES,
    PromptRole.CODE: PROXY_CODE,
    PromptRole.SYSTEM_DESIGN: PROXY_SYSTEM_DESIGN,
    PromptRole.SCREENSHOTS: "",
}
SKILL: Final = Label.of(Provenance.SKILL_USER)


@dataclass(frozen=True, slots=True)
class StudioLayers:
    """The platform layer, the person's words and their prompt for the role."""

    layer: str = ""
    context: str = ""
    prompt: RolePrompt = field(default_factory=lambda: RolePrompt(None))


async def studio_layers(
    ports: PortDirectory, session: AsyncSession, user_id: UUID, role: PromptRole
) -> StudioLayers:
    """What studio holds for the answer, read in the person's transaction; none without studio."""
    resolvers = ports.all(PROMPT_RESOLVER)
    if not resolvers:
        return StudioLayers()
    resolver = resolvers[0]
    layer = (await resolver.platform_layer()).text
    context = await resolver.personal_context(session, user_id, role)
    return StudioLayers(layer, context, await resolver.role_prompt(session, user_id, role))


def system_messages(frame: str, role: PromptRole, layers: StudioLayers) -> tuple[ChatMessage, ...]:
    """The answer's system messages in studio's order; empty parts are left out."""
    head = "\n\n".join(part for part in (frame, layers.layer) if part)
    messages = [said(Role.SYSTEM, head)]
    if layers.context:
        messages.append(said(Role.SYSTEM, PERSONAL_CONTEXT.format(context=layers.context)))
    body = layers.prompt.body if layers.prompt.body else BUILT_IN[role]
    parts = [body] if body else []
    if layers.prompt.skills:
        token = boundary(secrets.token_bytes(BOUNDARY_BYTES))
        parts.append(PROXY_SKILLS)
        parts.extend(
            wrap(SKILL_HEADING.format(name=skill.name, body=skill.body.strip()), SKILL, token)
            for skill in layers.prompt.skills
        )
    if parts:
        messages.append(said(Role.SYSTEM, "\n\n".join(parts)))
    return tuple(messages)
