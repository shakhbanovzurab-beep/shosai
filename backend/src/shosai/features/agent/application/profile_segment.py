"""Segment 4 of a Leo turn's head: the person, their zone, the answer's terms, memory and their
own words about themselves (Leo §7.3, studio ST-D7: ≤ 3 200 tokens with the context)."""

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.context_parts import UTC_ZONE, person_of
from shosai.features.agent.application.memory_context import MemoryContext
from shosai.features.agent.application.studio_context import personal_context
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.domain.context import profile_core
from shosai.features.agent.domain.memory_text import MemoryBlock
from shosai.features.agent.infrastructure.prompts import turn_instructions
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER


async def profile_segment(
    parts: tuple[PortDirectory, MemoryContext], session: AsyncSession, payload: TurnPayload
) -> tuple[str, str, MemoryBlock]:
    """Segment 4's text, the person's zone, and what memory put in it."""
    ports, memory = parts
    user_id = person_of(payload)
    profile = await ports.get(ACCOUNT_PROFILE_READER).profile(session, user_id)
    zone = profile.timezone if profile is not None and profile.timezone else UTC_ZONE
    core = profile_core(
        profile.display_name if profile is not None else "",
        zone,
        turn_instructions(payload.language, payload.length),
    )
    remembered = await memory.profile(session, payload)
    own = await personal_context(ports, session, user_id)
    return "\n".join(part for part in (core, remembered.text, own) if part), zone, remembered
