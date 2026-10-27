"""The facts the summary's writer and the "Ask or update" box read (memory step 7).

The person's current facts in Personal and the workspaces they are in now — at most 200, the
pinned first and then by how much of each is left — each on its own line under a short
reference (`F7 [kind] statement`), a meeting's marked as what others said. The references
stay on the server: the box's answer names them and only those it was given count. The
digest is taken of every current fact in the database, so the summary knows it is stale
after any change, whoever made it.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import Text, func, literal, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.fact_rows import FACT, fact_of, visible
from shosai.features.memory.domain.decay import retention
from shosai.features.memory.domain.facts import Fact, FactStatus, MemorySource

SUMMARY_FACTS: Final = 200
# Отпечаток без фактов: пустая память пишет пустую сводку без модели.
NO_FACTS_DIGEST: Final = ""


@dataclass(frozen=True, slots=True)
class HeldFacts:
    """The facts a model reads, their lines, their references and the digest of them all."""

    facts: tuple[Fact, ...]
    text: str
    refs: dict[str, UUID]
    digest: str


def line_of(ref: str, fact: Fact) -> str:
    """One fact as the model reads it."""
    meeting = " (meeting)" if fact.source is MemorySource.MEETING else ""
    return f"{ref} [{fact.kind.value}] {fact.statement}{meeting}"


async def digest_of(session: AsyncSession, user_id: UUID, spaces: frozenset[UUID]) -> str:
    """A fingerprint of the person's current facts: their ids, statements and pins."""
    piece = (
        FACT.id.cast(Text)
        + literal(":")
        + func.md5(FACT.statement)
        + literal(":")
        + FACT.pinned.cast(Text)
    )
    found = await session.scalar(
        select(func.md5(func.string_agg(piece, aggregate_order_by(literal(","), FACT.id)))).where(
            visible(user_id, spaces), FACT.status == FactStatus.ACTIVE.value
        )
    )
    return found or NO_FACTS_DIGEST


class SummaryFacts:
    """Reads the facts for the summary and the box."""

    def __init__(
        self, lists: FactLists, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._lists = lists
        self._clock = clock

    async def digest(self, session: AsyncSession, user_id: UUID) -> str:
        """The fingerprint of the person's current facts now."""
        return await digest_of(session, user_id, await self._lists.spaces(session, user_id))

    async def held(self, session: AsyncSession, user_id: UUID) -> HeldFacts:
        """The facts the model reads, in the order it reads them."""
        spaces = await self._lists.spaces(session, user_id)
        rows = await session.scalars(
            select(FACT).where(visible(user_id, spaces), FACT.status == FactStatus.ACTIVE.value)
        )
        now = self._clock()
        ordered = sorted(
            (fact_of(row) for row in rows),
            key=lambda fact: (not fact.pinned, -retention(fact, now), str(fact.id)),
        )[:SUMMARY_FACTS]
        refs = {f"F{index}": fact.id for index, fact in enumerate(ordered, start=1)}
        text = "\n".join(line_of(ref, fact) for ref, fact in zip(refs, ordered, strict=True))
        return HeldFacts(tuple(ordered), text, refs, await digest_of(session, user_id, spaces))
