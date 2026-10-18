"""A person's usage counters, changed by single statements in the caller's transaction.

A reservation is one conditional upsert: it adds the bytes only while used + reserved +
the bytes fit the limit, so concurrent uploads never pass it (the draft's rule). Release
and settlement never take a counter below zero; the database checks it too.

A person's locks are taken in one order — the Leo lock, then the usage row (`lock`), then
the person's files — so day 90's removal, which locks the row and then every file, never
deadlocks with a copy, a deletion or a restore.
"""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.files.infrastructure.upload_records import StorageUsageRecord

USAGE = StorageUsageRecord


async def lock(session: AsyncSession, user_id: UUID) -> None:
    """Hold the person's usage row until the transaction ends, before any of their files.

    A person without the row has no file to lock either; the statement then holds nothing.
    """
    await session.execute(select(USAGE.user_id).where(USAGE.user_id == user_id).with_for_update())


async def reserve(session: AsyncSession, user_id: UUID, size: int, limit: int | None) -> bool:
    """Reserve `size` bytes for the person; False when they would pass the limit."""
    if limit is not None and size > limit:
        return False
    fits = None if limit is None else USAGE.used_bytes + USAGE.reserved_bytes + size <= limit
    statement = (
        insert(USAGE)
        .values(user_id=user_id, reserved_bytes=size)
        .on_conflict_do_update(
            index_elements=[USAGE.user_id],
            set_={"reserved_bytes": USAGE.reserved_bytes + size, "updated_at": func.now()},
            where=fits,
        )
        .returning(USAGE.user_id)
    )
    return (await session.scalar(statement)) is not None


async def release(session: AsyncSession, user_id: UUID, size: int) -> None:
    """End a reservation without a file."""
    await session.execute(
        update(USAGE)
        .where(USAGE.user_id == user_id)
        .values(reserved_bytes=func.greatest(USAGE.reserved_bytes - size, 0), updated_at=func.now())
    )


async def settle(session: AsyncSession, user_id: UUID, size: int) -> None:
    """A reservation became a file: its bytes move from reserved to used."""
    await session.execute(
        update(USAGE)
        .where(USAGE.user_id == user_id)
        .values(
            reserved_bytes=func.greatest(USAGE.reserved_bytes - size, 0),
            used_bytes=USAGE.used_bytes + size,
            updated_at=func.now(),
        )
    )


async def charge(session: AsyncSession, user_id: UUID, size: int, limit: int | None) -> bool:
    """Add a new file's bytes to used while they fit the limit (a copy); False when not."""
    if limit is not None and size > limit:
        return False
    fits = None if limit is None else USAGE.used_bytes + USAGE.reserved_bytes + size <= limit
    statement = (
        insert(USAGE)
        .values(user_id=user_id, used_bytes=size)
        .on_conflict_do_update(
            index_elements=[USAGE.user_id],
            set_={"used_bytes": USAGE.used_bytes + size, "updated_at": func.now()},
            where=fits,
        )
        .returning(USAGE.user_id)
    )
    return (await session.scalar(statement)) is not None


async def add_used(session: AsyncSession, user_id: UUID, size: int) -> None:
    """Add bytes to used whatever the limit (a restored file); the quota rules act on it."""
    await session.execute(
        insert(USAGE)
        .values(user_id=user_id, used_bytes=size)
        .on_conflict_do_update(
            index_elements=[USAGE.user_id],
            set_={"used_bytes": USAGE.used_bytes + size, "updated_at": func.now()},
        )
    )


async def free(session: AsyncSession, user_id: UUID, size: int) -> None:
    """A file left the quota (hidden): its bytes are free again."""
    await session.execute(
        update(USAGE)
        .where(USAGE.user_id == user_id)
        .values(used_bytes=func.greatest(USAGE.used_bytes - size, 0), updated_at=func.now())
    )
