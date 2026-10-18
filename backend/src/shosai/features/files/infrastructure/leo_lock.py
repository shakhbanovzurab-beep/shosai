"""One person's changes of Leo's use, one at a time: a lock held until the transaction ends.

Whether Leo uses a file depends on the file and its folder, so two changes made at once —
a folder switched on while a file moves into it — could each miss the other: neither would
announce the file nor count it against the knowledge limit. Every change of Leo's use takes
this lock as its first statement, before it reads anything it decides on; no other
transaction takes it, so it never waits on a row lock held by one. A transaction-scoped
advisory lock needs no row and is released by commit or rollback, also behind PgBouncer.
"""

from typing import Final
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Пространство ключей блокировок files (ASCII «Leo»); второй ключ — id человека, свёрнутый
# в 32 бита: совпадение у двух людей лишь сериализует их изменения.
LEO_LOCK_SPACE: Final = 0x4C656F
WORD: Final = 2**32


def person_key(user_id: UUID) -> int:
    """The person's half of the lock key: the id folded into a signed 32-bit integer.

    Folding takes every bit, so ids of version 7 made in the same minute, which share their
    leading time bits, still get different keys.
    """
    folded = user_id.int
    folded ^= folded >> 64
    folded ^= folded >> 32
    folded %= WORD
    return folded - WORD if folded >= WORD // 2 else folded


async def hold_leo_lock(session: AsyncSession, user_id: UUID) -> None:
    """Wait for and hold the person's Leo lock until the caller's transaction ends."""
    await session.execute(select(func.pg_advisory_xact_lock(LEO_LOCK_SPACE, person_key(user_id))))
