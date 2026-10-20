"""One person's new templates, one at a time: a lock held until the transaction ends.

A person keeps at most 50 templates; two creates at once would each count 49 and both
add one. Every create takes this lock before it counts, so the second waits for the first
to commit. A transaction-scoped advisory lock needs no row and is released by commit or
rollback, also behind PgBouncer; the person's half of the key is PostgreSQL's `hashtext`
of their id, and two people sharing it only wait for each other.
"""

from typing import Final
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Пространство ключей блокировок шаблонов встреч (ASCII «Tpl»).
TEMPLATES_LOCK_SPACE: Final = 0x54706C


async def hold_template_lock(session: AsyncSession, user_id: UUID) -> None:
    """Wait for and hold the person's template lock until the caller's transaction ends."""
    key = func.hashtext(str(user_id))
    await session.execute(select(func.pg_advisory_xact_lock(TEMPLATES_LOCK_SPACE, key)))
