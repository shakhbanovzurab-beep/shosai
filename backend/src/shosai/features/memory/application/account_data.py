"""Memory's handler of a person's data: their facts, their switch and their summary.

Every fact — current, waiting or ended — is the person's data: the export lists them with
their kind, status, source and dates, never their vectors, which are derived; erasure deletes
every row and the "has memories" bit; a transfer copies the rows with their vectors, so the
other home recalls them without a single embedding call. A repeat deletes or adds nothing.
"""

from collections.abc import AsyncIterator, Mapping
from typing import Final, cast

from redis.asyncio import Redis
from sqlalchemy import Table, delete

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.db.model_base import ModelBase
from shosai.core.db.person_rows import (
    PersonRows,
    copy_person_rows,
    person_digest,
    person_lines,
    tables_holding,
    whole_rows,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.memory.infrastructure.presence import has_memories_key
from shosai.features.memory.infrastructure.records import (
    MEMORY_MODELS,
    MemoryFactRecord,
    MemorySettingsRecord,
    MemorySummaryRecord,
)

OWNER: Final = "memory"
ACCOUNT_DATA: Final = AccountDataSpec(
    OWNER, tuple(TableCoverage(model.__tablename__, Treatment.ERASE) for model in MEMORY_MODELS)
)
# Вектор выводится из утверждения: в архиве он не нужен человеку и не читается.
DERIVED: Final = frozenset({"embedding", "embedding_model"})
KEYS: Final[Mapping[type[ModelBase], str]] = {
    MemoryFactRecord: "id",
    MemorySettingsRecord: "user_id",
    MemorySummaryRecord: "user_id",
}


def _table(model: type[ModelBase]) -> Table:
    return cast("Table", model.__table__)


def _exported(model: type[ModelBase]) -> PersonRows:
    rows = whole_rows(_table(model), KEYS[model])
    columns = tuple(name for name in rows.columns if name not in DERIVED)
    return PersonRows(table=rows.table, columns=columns, key=rows.key)


EXPORTED: Final = tuple(_exported(model) for model in MEMORY_MODELS)
COPIED: Final = tuple(whole_rows(_table(model), KEYS[model]) for model in MEMORY_MODELS)


class MemoryAccountData:
    """The `core.account_data_handlers` binding of memory."""

    def __init__(self, transactions: HomeTransactions, valkey: Redis) -> None:
        self._transactions = transactions
        self._valkey = valkey

    @property
    def owner(self) -> str:
        """The slice's declaration."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """One JSON Lines file per table of the person's rows, without vectors."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in EXPORTED:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)

    async def erase(self, account: AccountRef) -> None:
        """Delete the person's rows in their home and their "has memories" bit."""
        await self.purge(account)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """Copy every row of the person to the other home, vectors included."""
        for rows in COPIED:
            await copy_person_rows(
                self._transactions, rows, account.user_id, (account.home, to_home)
            )

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of each table's rows of the person in `account.home`."""
        scope = TenancyScope(account.home, account.user_id)
        return {
            rows.table.name: await person_digest(self._transactions, scope, rows, account.user_id)
            for rows in COPIED
        }

    async def purge(self, account: AccountRef) -> None:
        """Delete the person's rows in `account.home`, then the bit in Valkey."""
        user_id = account.user_id
        async with self._transactions.begin(TenancyScope(account.home, user_id)) as session:
            for model in MEMORY_MODELS:
                table = _table(model)
                await session.execute(delete(table).where(table.c.user_id == user_id))
        await self._valkey.delete(has_memories_key(user_id))

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """The tables still holding the person's rows."""
        scope = TenancyScope(account.home, account.user_id)
        tables = [_table(model) for model in MEMORY_MODELS]
        return await tables_holding(self._transactions, scope, tables, account.user_id)
