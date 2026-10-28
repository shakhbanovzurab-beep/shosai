"""A grant or an app newly needing its person, told once (CN-D11, plan §3.5).

A grant breaks for all its apps — a refused refresh, a 401 with a fresh token — and an app
alone lacks a scope. Each write is one conditional update from `active`, so concurrent
failures break a grant once; `connectors.connection.broken` goes out for every app that
newly shows the problem, none for an app that already waited for its person. A transient
failure only counts, it never breaks anything.
"""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.outbox import EventOutbox
from shosai.features.connectors.contracts.events import ConnectionBroken
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.domain.states import (
    GRANT_PROBLEMS,
    ConnectionStatus,
    GrantStatus,
    Problem,
    connection_broken,
)
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord, GrantRecord


async def break_grant(
    session: AsyncSession, outbox: EventOutbox, grant_id: UUID, problem: Problem
) -> int:
    """Mark a working grant as needing its person; how many apps newly show it."""
    if problem not in GRANT_PROBLEMS:
        message = f"проблема {problem} принадлежит приложению, не гранту"
        raise ValueError(message)
    marked = await session.execute(
        update(GrantRecord)
        .where(GrantRecord.id == grant_id, GrantRecord.status == GrantStatus.ACTIVE.value)
        .values(
            status=GrantStatus.NEEDS_RECONNECT.value, problem=problem.value, updated_at=func.now()
        )
        .returning(GrantRecord.id)
    )
    if marked.first() is None:
        return 0
    apps = await session.execute(
        select(
            ConnectionRecord.id, ConnectionRecord.user_id, ConnectionRecord.org_id,
            ConnectionRecord.app,
        ).where(
            ConnectionRecord.grant_id == grant_id,
            ConnectionRecord.status == ConnectionStatus.ACTIVE.value,
        )
    )  # fmt: skip
    events = [
        ConnectionBroken(
            connection_id=row.id, user_id=row.user_id, org_id=row.org_id, app=App(row.app),
            problem=problem,
        )
        for row in apps
    ]  # fmt: skip
    if events:
        await outbox.add_all(session, events)
    return len(events)


async def break_connection(
    session: AsyncSession, outbox: EventOutbox, connection_id: UUID, problem: Problem
) -> bool:
    """Mark one working app as lacking what it needs; whether that is news."""
    state = connection_broken(problem)
    marked = await session.execute(
        update(ConnectionRecord)
        .where(
            ConnectionRecord.id == connection_id,
            ConnectionRecord.status == ConnectionStatus.ACTIVE.value,
        )
        .values(status=state.status.value, problem=problem.value, updated_at=func.now())
        .returning(
            ConnectionRecord.user_id, ConnectionRecord.org_id, ConnectionRecord.app,
            ConnectionRecord.grant_id,
        )
    )  # fmt: skip
    row = marked.first()
    if row is None:
        return False
    grant_status = await session.scalar(
        select(GrantRecord.status).where(GrantRecord.id == row.grant_id)
    )
    if grant_status != GrantStatus.ACTIVE.value:
        return False
    event = ConnectionBroken(
        connection_id=connection_id, user_id=row.user_id, org_id=row.org_id, app=App(row.app),
        problem=problem,
    )  # fmt: skip
    await outbox.add(session, event)
    return True


async def count_failure(session: AsyncSession, grant_id: UUID) -> None:
    """One more transient failure of a grant; nothing breaks."""
    await session.execute(
        update(GrantRecord)
        .where(GrantRecord.id == grant_id)
        .values(
            consecutive_failures=GrantRecord.consecutive_failures + 1, last_failure_at=func.now()
        )
    )
