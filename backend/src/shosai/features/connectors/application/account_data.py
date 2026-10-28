"""Connectors' handler of a person's data: their grants, the grants' secrets, their apps.

Only personal rows are the person's: a workspace's installation they made belongs to the
workspace and stays when they leave or are erased (CN-D3). The export lists grants, the
secrets' dates and connections, never a ciphertext; a transfer copies every row with its
ciphertexts unchanged, since one key ring serves both homes; erasure first asks each provider
once to revoke the person's grants, then deletes the person's personal rows. A repeat deletes
or adds nothing.
"""

from collections.abc import AsyncIterator, Mapping
from typing import Final, cast
from uuid import UUID

from sqlalchemy import ColumnElement, Table, delete, exists, select

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.db.person_rows import (
    PersonRows,
    copy_person_rows,
    person_digest,
    person_lines,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.revocation import GrantRevoker
from shosai.features.connectors.infrastructure.store.records import (
    CONNECTOR_MODELS,
    ConnectionRecord,
    GrantRecord,
    GrantSecretRecord,
)

OWNER: Final = "connectors"
ACCOUNT_DATA: Final = AccountDataSpec(
    OWNER,
    tuple(TableCoverage(model.__tablename__, Treatment.ERASE) for model in CONNECTOR_MODELS),
    external_grants=("oauth grants and app passwords of the person's connections",),
)
GRANTS: Final = cast("Table", GrantRecord.__table__)
SECRETS: Final = cast("Table", GrantSecretRecord.__table__)
CONNECTIONS: Final = cast("Table", ConnectionRecord.__table__)


def personal(table: Table) -> ColumnElement[bool]:
    """The rows of a table that are a person's own, not a workspace's."""
    return table.c.org_id.is_(None)


def _rows(table: Table, key: str, columns: tuple[str, ...] | None = None) -> PersonRows:
    names = columns if columns is not None else tuple(table.columns.keys())
    return PersonRows(table, names, key=key, only=lambda _person: personal(table))


# Выгрузка — без шифртекстов и аренды обновления.
EXPORTED: Final = (
    _rows(GRANTS, "id", (
        "id", "provider", "auth_kind", "external_account_id", "account_label",
        "granted_scopes", "status", "problem", "created_at", "updated_at",
    )),
    # Только сроки: сами шифртексты в архив не попадают.
    _rows(SECRETS, "grant_id", ("grant_id", "expires_at", "refreshed_at")),
    _rows(CONNECTIONS, "id", (
        "id", "app", "grant_id", "status", "problem", "last_used_at", "connected_at",
    )),
)  # fmt: skip
# Перенос — целые строки в порядке ключей: грант, его секреты, приложения на нём.
MOVED: Final = (_rows(GRANTS, "id"), _rows(SECRETS, "grant_id"), _rows(CONNECTIONS, "id"))


class ConnectorsAccountData:
    """The `core.account_data_handlers` binding of connectors."""

    def __init__(self, transactions: HomeTransactions, revoker: GrantRevoker | None = None) -> None:
        # Без отзывающего (в тестах таблиц) стирание удаляет только строки.
        self._transactions = transactions
        self._revoker = revoker

    @property
    def owner(self) -> str:
        """The slice's declaration."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """One JSON Lines file per table, without secrets."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in EXPORTED:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)

    async def erase(self, account: AccountRef) -> None:
        """Revoke the person's grants at their providers once, then delete their rows."""
        if self._revoker is not None:
            scope = TenancyScope(account.home, account.user_id)
            query = select(GRANTS.c.id).where(GRANTS.c.user_id == account.user_id, personal(GRANTS))
            async with self._transactions.begin(scope, read_only=True) as session:
                grant_ids = list((await session.execute(query)).scalars().all())
            await self._revoker.revoke_all(scope, grant_ids)
        await self.purge(account)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """Copy the person's rows to the other home, ciphertexts unchanged."""
        for rows in MOVED:
            await copy_person_rows(
                self._transactions, rows, account.user_id, (account.home, to_home)
            )

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of each moved table's rows of the person in `account.home`."""
        scope = TenancyScope(account.home, account.user_id)
        return {
            rows.table.name: await person_digest(self._transactions, scope, rows, account.user_id)
            for rows in MOVED
        }

    async def purge(self, account: AccountRef) -> None:
        """Delete the person's personal rows in `account.home`, apps before their grants."""
        user_id = account.user_id
        async with self._transactions.begin(TenancyScope(account.home, user_id)) as session:
            for table in (CONNECTIONS, GRANTS):
                await session.execute(
                    delete(table).where(table.c.user_id == user_id, personal(table))
                )

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """The tables still holding a personal row of the person."""
        tables = (GRANTS, SECRETS, CONNECTIONS)
        checks = [holds(table, account.user_id).label(table.name) for table in tables]
        scope = TenancyScope(account.home, account.user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            found = (await session.execute(select(*checks))).one()
        return tuple(table.name for table, held in zip(tables, found, strict=True) if held)


def holds(table: Table, user_id: UUID) -> ColumnElement[bool]:
    """Whether the table holds a personal row of the person."""
    return exists().where(table.c.user_id == user_id, personal(table))
