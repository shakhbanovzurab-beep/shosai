"""What studio adds to a Leo turn's head and to Leo's voice (studio plan §3.4, ADR 0074 ST-D7).

Segment 1 takes the operator's published platform layer after the policy core; segment 4 takes
the person's own words about themselves after the profile core and memory. Both are stable
between turns and sit before the provider's cache breakpoint. Leo's voice takes the layer, the
`voice_mode` addendum and the person's words after its own instruction. The operator's own
turns take none of it: the layer is for people, and the operator has no Studio. Without studio
in the process the head is as before.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.domain.operator import is_operator
from shosai.features.agent.infrastructure.prompts import PERSONAL_CONTEXT
from shosai.features.studio.contracts import PROMPT_RESOLVER, PlatformFeature


async def platform_layer(ports: PortDirectory, user_id: UUID) -> str:
    """The published platform layer for a person's turn; empty before a publish."""
    resolvers = ports.all(PROMPT_RESOLVER)
    if not resolvers or is_operator(user_id):
        return ""
    return (await resolvers[0].platform_layer()).text


async def personal_context(ports: PortDirectory, session: AsyncSession, user_id: UUID) -> str:
    """The person's words about themselves, framed for segment 4; empty when they wrote none."""
    resolvers = ports.all(PROMPT_RESOLVER)
    if not resolvers or is_operator(user_id):
        return ""
    text = await resolvers[0].personal_context(session, user_id)
    return PERSONAL_CONTEXT.format(context=text) if text else ""


async def voice_layers(ports: PortDirectory, session: AsyncSession, user_id: UUID) -> str:
    """What studio adds after Leo's voice instruction: the layer, the addendum, the words."""
    resolvers = ports.all(PROMPT_RESOLVER)
    if not resolvers or is_operator(user_id):
        return ""
    resolver = resolvers[0]
    layer = (await resolver.platform_layer()).text
    addendum = await resolver.feature_prompt(PlatformFeature.VOICE_MODE)
    own = await personal_context(ports, session, user_id)
    return "\n\n".join(part for part in (layer, addendum, own) if part)
