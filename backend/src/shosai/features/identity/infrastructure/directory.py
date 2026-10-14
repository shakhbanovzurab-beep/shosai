"""The directory in the EU home: where each address's account lives (§6, §4.3, §13.2).

Sign-in reads it through a 60-second cache, and when the EU home does not answer it uses
the last copy it has, however old: a running sign-in is worth more than a few minutes of
freshness (§13.2). Registration and the claim of an address read the database itself and
fail with 503 when it is out of reach, because two registrations must never both win.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

import structlog
from sqlalchemy import delete, exc, select, update
from sqlalchemy.dialects.postgresql import insert

from shosai.core.cache.port import Cache, CacheKey
from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.identity.domain.registration import DirectoryState
from shosai.features.identity.infrastructure.records import DirectoryEntry

CACHE_NAMESPACE: Final = "directory.v1"
FRESH_FOR: Final = timedelta(seconds=60)
# Запасная копия на случай недоступного каталога: сутки, а свежей она считается 60 с.
KEPT_FOR: Final = timedelta(days=1)
DIRECTORY_SCOPE: Final = TenancyScope(Home.EU)
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DirectoryRecord:
    """An address's account, its home and its state."""

    user_id: UUID
    home: Home
    state: DirectoryState


class ClaimOutcome(StrEnum):
    """What claiming an address for an account gave."""

    WON = "won"
    # Повтор того же подтверждения: адрес уже за этим аккаунтом.
    ALREADY_OURS = "already_ours"
    TAKEN = "taken"


class Directory:
    """Reads and writes of the directory, with the cache of sign-in."""

    def __init__(self, transactions: HomeTransactions, cache: Cache) -> None:
        self._transactions = transactions
        self._cache = cache

    async def find(self, email_hmac: bytes) -> DirectoryRecord | None:
        """The entry for sign-in: cached for 60 s, the last copy when the EU home is down."""
        key = CacheKey(CACHE_NAMESPACE, email_hmac.hex())
        cached = _decode(await self._cache.get(key))
        if cached is not None and datetime.now(UTC) - cached[1] < FRESH_FOR:
            return cached[0]
        try:
            record = await self.find_fresh(email_hmac)
        except HomeUnavailableError:
            if cached is None:
                raise
            log.warning("Каталог недоступен, вход по копии из кеша")
            return cached[0]
        if record is not None:
            await self._cache.set(key, _encode(record), KEPT_FOR)
        return record

    async def find_fresh(self, email_hmac: bytes) -> DirectoryRecord | None:
        """The entry as the EU home has it now; 503 when the home does not answer."""
        try:
            async with self._transactions.begin(DIRECTORY_SCOPE, read_only=True) as session:
                row = await session.scalar(
                    select(DirectoryEntry).where(DirectoryEntry.email_hmac == email_hmac)
                )
        except exc.OperationalError as error:
            raise HomeUnavailableError(Home.EU) from error
        return None if row is None else _record(row)

    async def claim(self, email_hmac: bytes, user_id: UUID, home: Home) -> ClaimOutcome:
        """Take a free address for the account; an erased account's address is free again."""
        statement = (
            insert(DirectoryEntry)
            .values(
                email_hmac=email_hmac,
                user_id=user_id,
                home=home.value,
                state=DirectoryState.CLAIMED.value,
            )
            .on_conflict_do_update(
                index_elements=[DirectoryEntry.email_hmac],
                set_={
                    "user_id": user_id,
                    "home": home.value,
                    "state": DirectoryState.CLAIMED.value,
                    "version": DirectoryEntry.version + 1,
                    "updated_at": datetime.now(UTC),
                    "deleted_at": None,
                },
                where=DirectoryEntry.state == DirectoryState.DELETED.value,
            )
            .returning(DirectoryEntry.user_id)
        )
        async with self._transactions.begin(DIRECTORY_SCOPE) as session:
            if await session.scalar(statement) is not None:
                return ClaimOutcome.WON
            holder = await session.scalar(
                select(DirectoryEntry.user_id).where(DirectoryEntry.email_hmac == email_hmac)
            )
        return ClaimOutcome.ALREADY_OURS if holder == user_id else ClaimOutcome.TAKEN

    async def activate(self, email_hmac: bytes, user_id: UUID) -> None:
        """Mark a claimed address active once its account is committed in its home."""
        async with self._transactions.begin(DIRECTORY_SCOPE) as session:
            await session.execute(
                update(DirectoryEntry)
                .where(
                    DirectoryEntry.email_hmac == email_hmac,
                    DirectoryEntry.user_id == user_id,
                    DirectoryEntry.state == DirectoryState.CLAIMED.value,
                )
                .values(
                    state=DirectoryState.ACTIVE.value,
                    version=DirectoryEntry.version + 1,
                    updated_at=datetime.now(UTC),
                )
            )
        await self._cache.delete(CacheKey(CACHE_NAMESPACE, email_hmac.hex()))

    async def release(self, email_hmac: bytes, user_id: UUID) -> None:
        """Free an address claimed for an account that was never written."""
        async with self._transactions.begin(DIRECTORY_SCOPE) as session:
            await session.execute(
                delete(DirectoryEntry).where(
                    DirectoryEntry.email_hmac == email_hmac,
                    DirectoryEntry.user_id == user_id,
                    DirectoryEntry.state == DirectoryState.CLAIMED.value,
                )
            )

    async def stale_claims(self, older_than: datetime, limit: int) -> list[DirectoryEntry]:
        """Claims left unfinished: their verification stopped between the two homes."""
        async with self._transactions.begin(DIRECTORY_SCOPE, read_only=True) as session:
            rows = await session.scalars(
                select(DirectoryEntry)
                .where(
                    DirectoryEntry.state == DirectoryState.CLAIMED.value,
                    DirectoryEntry.updated_at < older_than,
                )
                .order_by(DirectoryEntry.updated_at)
                .limit(limit)
            )
            return list(rows)


def _record(row: DirectoryEntry) -> DirectoryRecord:
    return DirectoryRecord(row.user_id, Home(row.home), DirectoryState(row.state))


def _encode(record: DirectoryRecord) -> bytes:
    payload = {
        "user_id": str(record.user_id),
        "home": record.home.value,
        "state": record.state.value,
        "read_at": datetime.now(UTC).timestamp(),
    }
    return json.dumps(payload).encode("utf-8")


def _decode(value: bytes | None) -> tuple[DirectoryRecord, datetime] | None:
    if value is None:
        return None
    try:
        payload = json.loads(value)
        record = DirectoryRecord(
            UUID(payload["user_id"]), Home(payload["home"]), DirectoryState(payload["state"])
        )
        return record, datetime.fromtimestamp(float(payload["read_at"]), UTC)
    except ValueError, KeyError, TypeError:
        # Запись прежней формы: читается как промах, следующее чтение перепишет её.
        log.warning("Копия каталога в кеше не читается")
        return None
