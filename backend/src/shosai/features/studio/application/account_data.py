"""Studio's handler of a person's data: their context, prompts and model settings.

Everything a person wrote in Studio is theirs: the export lists every table whole, erasure
deletes every row, and a transfer copies them in the order their keys need — prompts before
their skills and the roles they serve. The skills themselves are agent's rows and move with
agent under the same ids. A repeat deletes or adds nothing.
"""

from collections.abc import AsyncIterator, Mapping
from typing import Final, cast

from sqlalchemy import Table, delete

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.db.model_base import ModelBase
from shosai.core.db.person_rows import (
    copy_person_rows,
    person_digest,
    person_lines,
    tables_holding,
    whole_rows,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.studio.infrastructure.person_records import (
    PERSON_MODELS,
    ContextRecord,
    PromptRecord,
    PromptSkillRecord,
    RoleModelRecord,
    RolePromptRecord,
)

OWNER: Final = "studio"
ACCOUNT_DATA: Final = AccountDataSpec(
    OWNER, tuple(TableCoverage(model.__tablename__, Treatment.ERASE) for model in PERSON_MODELS)
)
# Уникальный ключ строк человека, по которому их листают; порядок — порядок внешних ключей.
KEYS: Final[Mapping[type[ModelBase], str]] = {
    ContextRecord: "user_id",
    PromptRecord: "id",
    PromptSkillRecord: "id",
    RolePromptRecord: "role",
    RoleModelRecord: "role",
}


def _table(model: type[ModelBase]) -> Table:
    return cast("Table", model.__table__)


ROWS: Final = tuple(whole_rows(_table(model), key) for model, key in KEYS.items())


class StudioAccountData:
    """The `core.account_data_handlers` binding of studio."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    @property
    def owner(self) -> str:
        """The slice's declaration."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """One JSON Lines file per table of the person's rows."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in ROWS:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)

    async def erase(self, account: AccountRef) -> None:
        """Delete the person's rows in their home."""
        await self.purge(account)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """Copy every row of the person to the other home, prompts before what needs them."""
        for rows in ROWS:
            await copy_person_rows(
                self._transactions, rows, account.user_id, (account.home, to_home)
            )

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of each table's rows of the person in `account.home`."""
        scope = TenancyScope(account.home, account.user_id)
        return {
            rows.table.name: await person_digest(self._transactions, scope, rows, account.user_id)
            for rows in ROWS
        }

    async def purge(self, account: AccountRef) -> None:
        """Delete the person's rows in `account.home`, what needs a prompt first."""
        user_id = account.user_id
        async with self._transactions.begin(TenancyScope(account.home, user_id)) as session:
            for rows in reversed(ROWS):
                await session.execute(delete(rows.table).where(rows.table.c.user_id == user_id))

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """The tables still holding the person's rows."""
        scope = TenancyScope(account.home, account.user_id)
        tables = [rows.table for rows in ROWS]
        return await tables_holding(self._transactions, scope, tables, account.user_id)
