"""A person's meetings while identity's deletion window runs (ADR 0045 point 6, MT-D8).

Notes keeps the window on the person's setting row from identity's events: scheduled
marks it, cancelled clears it. The row keeps the time of the last event applied, so events
delivered out of order end where the latest one says, and a repeat changes nothing. The
same transaction marks every personal meeting of the person, hidden ones included, so
`visible_meetings` serves them to nobody — their owner, a workspace they are shared in,
Leo, other slices — and their share links stop opening; a cancellation shows them again,
unchanged. A meeting made while the mark stands is made hidden. A workspace's meeting is
the workspace's and stays. While it is marked, support neither lists nor restores the
person's meetings.
"""

from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.notes.infrastructure.meeting_records import MeetingRecord
from shosai.features.notes.infrastructure.notes_records import SettingsRecord

log = structlog.stdlib.get_logger(__name__)
SETTINGS = SettingsRecord


async def apply_account_window(
    session: AsyncSession, user_id: UUID, *, hidden: bool, occurred_at: datetime
) -> bool:
    """Mark or clear the person's window; False when an event as new was applied before."""
    newer = or_(SETTINGS.account_event_at.is_(None), SETTINGS.account_event_at < occurred_at)
    applied = await session.scalar(
        insert(SETTINGS)
        .values(user_id=user_id, account_hidden=hidden, account_event_at=occurred_at)
        .on_conflict_do_update(
            index_elements=[SETTINGS.user_id],
            set_={
                "account_hidden": hidden,
                "account_event_at": occurred_at,
                "updated_at": func.now(),
            },
            where=newer,
        )
        .returning(SETTINGS.user_id)
    )
    if applied is None:
        log.info("Устаревшее событие окна удаления пропущено", user_id=str(user_id))
        return False
    # Через соединение: оператор ядра, и число отмеченных встреч известно без RETURNING.
    connection = await session.connection()
    marked = await connection.execute(
        update(MeetingRecord)
        .where(MeetingRecord.user_id == user_id, MeetingRecord.org_id.is_(None))
        .values(account_hidden=hidden)
    )
    log.info(
        "Окно удаления аккаунта для встреч",
        user_id=str(user_id), hidden=hidden, meetings=marked.rowcount,
    )  # fmt: skip
    return True


async def account_hidden(session: AsyncSession, user_id: UUID) -> bool:
    """Whether the person's account is in its deletion window now."""
    hidden = await session.scalar(
        select(SETTINGS.account_hidden).where(SETTINGS.user_id == user_id)
    )
    return bool(hidden)
