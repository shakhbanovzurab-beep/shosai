"""Claiming the due rows of a slice's table, once each under concurrency (§12, F6-C14).

A slice's sweep task calls `claim_due` in its transaction: it takes up to `limit` rows that
are pending and due, oldest first, skipping rows another sweep holds, and moves their
`run_at` forward by a lease. A claimed row stays pending, so a sweep that dies leaves it to
come due again when the lease ends — at-least-once, which the slice makes harmless with its
own state and effect keys; the sweep that finishes a row moves it out of pending. The
slice's table needs a unique key, a NOT NULL `timestamptz` due column and an index on
(due column, key) where pending.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import ColumnElement, Row, TableClause, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class DueRows:
    """A slice's table of rows that fall due: its key, its due column, its pending rows."""

    table: TableClause
    key: ColumnElement[Any]
    run_at: ColumnElement[Any]
    pending: ColumnElement[bool]


async def claim_due(
    session: AsyncSession, rows: DueRows, *, limit: int, lease: timedelta
) -> Sequence[Row[Any]]:
    """Claim up to `limit` due rows for `lease`; return them as they are after the claim."""
    if limit < 1 or lease <= timedelta(0):
        message = "захват строк: предел от одной строки, аренда больше нуля"
        raise ValueError(message)
    due = (
        select(rows.key)
        .where(rows.pending, rows.run_at <= func.now())
        .order_by(rows.run_at, rows.key)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    claim = (
        update(rows.table)
        .where(rows.key.in_(due))
        .values({rows.run_at: func.now() + lease})
        .returning(*rows.table.c)
    )
    return (await session.execute(claim)).all()
