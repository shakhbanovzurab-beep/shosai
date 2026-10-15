"""The sweeps behind registration: expired pending rows and unfinished directory claims.

A pending registration lives 15 minutes, extended by each resend; after that its row in
the home is deleted. A claim in the directory whose verification stopped between the
homes (a crash after step 2 of `verification.py`) is settled after 10 minutes: activated
when its account was written, released when it was not, so the address is never held
by an account that does not exist (inv-1; the monitor of §16.4).
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, select

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.records import PendingRegistration, User
from shosai.features.identity.infrastructure.session_records import RefreshSession

CLAIM_GRACE: Final = timedelta(minutes=10)
CLAIMS_PER_SWEEP: Final = 200
# Закончившиеся сессии видны в списке устройств ещё 30 дней, потом удаляются.
ENDED_SESSIONS_KEPT: Final = timedelta(days=30)
log = structlog.stdlib.get_logger(__name__)


async def purge_pending(transactions: HomeTransactions, home: Home) -> int:
    """Delete the home's expired pending registrations; the number deleted."""
    async with transactions.begin(TenancyScope(home)) as session:
        # Через соединение: оператор ядра, и известно число удалённых строк без RETURNING.
        connection = await session.connection()
        deleted = await connection.execute(
            delete(PendingRegistration).where(PendingRegistration.expires_at < datetime.now(UTC))
        )
        count = deleted.rowcount
    if count:
        log.info("Просроченные регистрации удалены", home=home.value, count=count)
    return count


async def settle_claims(transactions: HomeTransactions, directory: Directory) -> int:
    """Activate or release claims older than 10 minutes; the number settled."""
    claims = await directory.stale_claims(datetime.now(UTC) - CLAIM_GRACE, CLAIMS_PER_SWEEP)
    by_home: dict[Home, list[UUID]] = defaultdict(list)
    for claim in claims:
        by_home[Home(claim.home)].append(claim.user_id)
    written: set[UUID] = set()
    for home, user_ids in by_home.items():
        async with transactions.begin(TenancyScope(home), read_only=True) as session:
            found = await session.scalars(select(User.id).where(User.id.in_(user_ids)))
            written.update(found)
    for claim in claims:
        if claim.user_id in written:
            await directory.activate(claim.email_hmac, claim.user_id)
        else:
            await directory.release(claim.email_hmac, claim.user_id)
    if claims:
        log.warning(
            "Незавершённые заявки каталога разобраны",
            activated=len(written),
            released=len(claims) - len(written),
        )
    return len(claims)


async def purge_sessions(transactions: HomeTransactions, home: Home) -> int:
    """Delete families that expired or were revoked more than 30 days ago."""
    cutoff = datetime.now(UTC) - ENDED_SESSIONS_KEPT
    async with transactions.begin(TenancyScope(home)) as session:
        # Через соединение: оператор ядра, и известно число удалённых строк без RETURNING.
        connection = await session.connection()
        deleted = await connection.execute(
            delete(RefreshSession).where(
                (RefreshSession.expires_at < cutoff) | (RefreshSession.revoked_at < cutoff)
            )
        )
        return deleted.rowcount
