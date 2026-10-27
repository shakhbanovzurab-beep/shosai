"""Memory in the evaluation's world: on, as for every person who never switched it off, and
holding nothing a turn recalls by itself — a scenario's facts come only through its answers to
`memory.recall` (memory step 6)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.agent.contracts.memory import ProfileCore


class EvalMemory:
    """The `agent.profile_facts` binding of the evaluation."""

    async def profile(self, session: AsyncSession, user_id: UUID, max_tokens: int) -> ProfileCore:
        """Memory on, no pinned fact."""
        del session, user_id, max_tokens
        return ProfileCore(enabled=True, facts=())

    async def enabled(self, session: AsyncSession, user_id: UUID) -> bool:
        """On."""
        del session, user_id
        return True
