"""A person's files while identity's deletion window runs (ADR 0045 point 6, files step 7).

When identity schedules an account's deletion, every personal file of the person — hidden
ones included — is marked, and `visible_files` serves it to nobody: not its owner, not a
workspace it is shared in, not Leo, not a download, not background work. The daily
passes of FL-D2 and FL-D10 leave the person alone, so nothing is reminded or removed.
A cancellation shows everything again, unchanged. The usage row is locked first, as the
person's locks go, and keeps the time of the last account event applied, so events
delivered out of order end where the latest one says; a repeat changes nothing.
"""

from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import func, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.features.files.infrastructure.file_records import StorageFileRecord
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord

log = structlog.stdlib.get_logger(__name__)
USAGE = StorageUsageRecord


async def apply_account_window(
    session: AsyncSession, user_id: UUID, *, hidden: bool, occurred_at: datetime
) -> bool:
    """Hide or show the person's files in the caller's transaction of the person.

    False when an account event at least as new was applied before; nothing changes then.
    """
    newer = or_(USAGE.account_event_at.is_(None), USAGE.account_event_at < occurred_at)
    applied = await session.scalar(
        insert(USAGE)
        .values(user_id=user_id, account_hidden=hidden, account_event_at=occurred_at)
        .on_conflict_do_update(
            index_elements=[USAGE.user_id],
            set_={
                "account_hidden": hidden,
                "account_event_at": occurred_at,
                "updated_at": func.now(),
            },
            where=newer,
        )
        .returning(USAGE.user_id)
    )
    if applied is None:
        log.info("Устаревшее событие окна удаления пропущено", user_id=str(user_id))
        return False
    await session.execute(
        update(StorageFileRecord)
        .where(StorageFileRecord.user_id == user_id, StorageFileRecord.org_id.is_(None))
        .values(account_hidden=hidden)
    )
    log.info("Файлы аккаунта в окне удаления", user_id=str(user_id), hidden=hidden)
    return True
