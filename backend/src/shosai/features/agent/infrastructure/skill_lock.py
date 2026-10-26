"""One person's skill installs, one at a time: a lock held until the transaction ends.

The count of a person's skills is checked before the insert, so two installs at once could
each see 19 and both insert. Every install takes this lock first; nothing else takes it. A
transaction-scoped advisory lock needs no row and is released by commit or rollback, also
behind PgBouncer.
"""

from typing import Final
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Пространство ключей блокировок навыков (ASCII «Skl»); второй ключ — id человека в 32 битах.
SKILLS_LOCK_SPACE: Final = 0x536B6C
WORD: Final = 2**32


def person_key(user_id: UUID) -> int:
    """The person's half of the key: every bit of the id folded into a signed 32-bit integer."""
    folded = user_id.int
    folded ^= folded >> 64
    folded ^= folded >> 32
    folded %= WORD
    return folded - WORD if folded >= WORD // 2 else folded


async def hold_skills_lock(session: AsyncSession, user_id: UUID) -> None:
    """Wait for and hold the person's skills lock until the caller's transaction ends."""
    await session.execute(
        select(func.pg_advisory_xact_lock(SKILLS_LOCK_SPACE, person_key(user_id)))
    )
