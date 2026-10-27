"""What memory adds to a turn: the profile core and the recalled facts (Leo §7.3, step 4).

The profile core is read in the context's own transaction and closes segment 4 with whether
memory is on and the pinned facts and preferences, under a boundary keyed to their text.
Recall starts as soon as the question and the previous answer are read, beside the rest of
the context, and is awaited after the transaction: the embedding call never holds a database
connection. A recall that is late, failed or absent gives nothing; the turn goes on. Whether
memory is on is also read when a turn starts, so the turn carries memory's switch and offers its
toolset only then.
"""

import asyncio
import secrets
from collections.abc import Sequence
from datetime import timedelta
from functools import partial
from typing import Final
from uuid import UUID

import structlog
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.turn_task import TurnPayload
from shosai.features.agent.contracts.memory import (
    MEMORY_RECALL,
    MEMORY_SWITCH,
    PROFILE_FACTS,
    RecalledFact,
    RecallRequest,
)
from shosai.features.agent.domain.memory_text import MemoryBlock, memory_block
from shosai.features.agent.domain.operator import is_operator
from shosai.features.agent.domain.wrapper import BOUNDARY_BYTES, boundary, keyed_boundary
from shosai.features.agent.infrastructure.prompts import (
    MEMORY_LINE,
    MEMORY_OFF,
    MEMORY_ON,
    RECALLED,
    REMEMBERED,
)

# Доля сегмента 4 для памяти: остальное — имя, зона, язык и длина ответа.
PROFILE_SHARE: Final = 400
RECALL_TOKENS: Final = 600
RECALL_DEADLINE: Final = timedelta(milliseconds=350)
# Запас поверх срока вспоминания: память сама укладывается в срок, это страховка хода.
GRACE: Final = timedelta(milliseconds=100)
ANSWER_HEAD: Final = 300
type Recalling = asyncio.Task[tuple[RecalledFact, ...]]
log = structlog.stdlib.get_logger(__name__)


async def memory_switches(
    ports: PortDirectory, session: AsyncSession, user_id: UUID
) -> tuple[str, ...]:
    """The memory switch while the person's memory is on: it offers memory's toolset."""
    bound = ports.all(PROFILE_FACTS)
    if not bound or is_operator(user_id):
        return ()
    return (MEMORY_SWITCH,) if await bound[0].enabled(session, user_id) else ()


class MemoryContext:
    """Memory's part of a turn's context, when memory is bound."""

    def __init__(self, ports: PortDirectory, key: bytes) -> None:
        self._ports = ports
        self._key = key

    async def profile(self, session: AsyncSession, payload: TurnPayload) -> MemoryBlock:
        """Segment 4's memory lines: whether memory is on and the facts under a keyed boundary."""
        bound = self._ports.all(PROFILE_FACTS)
        if not bound or payload.user_id is None or is_operator(payload.user_id):
            return MemoryBlock("", ())
        core = await bound[0].profile(session, payload.user_id, PROFILE_SHARE)
        if not core.enabled:
            return MemoryBlock(MEMORY_OFF, (), on=False)
        facts = memory_block(
            core.facts, (REMEMBERED, MEMORY_LINE), partial(keyed_boundary, self._key)
        )
        text = "\n".join(part for part in (MEMORY_ON, facts.text) if part)
        return MemoryBlock(text, facts.tainting)

    def recall(self, payload: TurnPayload, question: str, earlier: str) -> Recalling | None:
        """Start recalling for the question with the start of the previous answer."""
        bound = self._ports.all(MEMORY_RECALL)
        if not bound or payload.user_id is None or is_operator(payload.user_id):
            return None
        request = RecallRequest(
            home=payload.home,
            user_id=payload.user_id,
            query="\n".join(part for part in (question, earlier[:ANSWER_HEAD]) if part),
            cross_border_consent=payload.cross_border_consent,
            max_tokens=RECALL_TOKENS,
            deadline=RECALL_DEADLINE,
        )
        return asyncio.create_task(bound[0].recall(request))

    async def recalled(self, pending: Sequence[Recalling]) -> MemoryBlock:
        """The recalled facts as segment 7's block, or nothing when there are none in time."""
        facts: tuple[RecalledFact, ...] = ()
        for task in pending:
            try:
                async with asyncio.timeout((RECALL_DEADLINE + GRACE).total_seconds()):
                    facts += await task
            except TimeoutError:
                task.cancel()
            except (SQLAlchemyError, RedisError, OSError) as error:
                log.warning("Вспоминание для хода не удалось", error=type(error).__name__)
        token = boundary(secrets.token_bytes(BOUNDARY_BYTES))
        return memory_block(facts, (RECALLED, MEMORY_LINE), lambda _: token)
