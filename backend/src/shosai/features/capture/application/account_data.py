"""Capture's handler of a person's data: the minutes of their voice conversations.

Export gives the table, erasure deletes the person's rows in their home, and a transfer
copies them whole — the month's minutes go with the person — and purges the source.
"""

from collections.abc import AsyncIterator, Mapping
from typing import Final

from sqlalchemy import delete

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
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
from shosai.features.capture.infrastructure.voice_records import VoiceSessionRecord

OWNER: Final = "capture"
SESSIONS: Final = VoiceSessionRecord
ACCOUNT_DATA: Final = AccountDataSpec(
    OWNER, (TableCoverage(SESSIONS.__tablename__, Treatment.ERASE),)
)
TABLE: Final = SESSIONS.metadata.tables[SESSIONS.__tablename__]
ROWS: Final = whole_rows(TABLE, key="id")


class CaptureAccountData:
    """The `core.account_data_handlers` binding of capture."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    @property
    def owner(self) -> str:
        """Capture's declaration."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """One JSON Lines file of the conversations."""
        scope = TenancyScope(account.home, account.user_id)
        lines = person_lines(self._transactions, scope, ROWS, account.user_id)
        yield ExportFile(f"{TABLE.name}.jsonl", lines)

    async def erase(self, account: AccountRef) -> None:
        """Delete the person's conversations in their home."""
        await self.purge(account)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """Copy the conversations to the other home."""
        await copy_person_rows(self._transactions, ROWS, account.user_id, (account.home, to_home))

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of the table in the person's home."""
        scope = TenancyScope(account.home, account.user_id)
        return {TABLE.name: await person_digest(self._transactions, scope, ROWS, account.user_id)}

    async def purge(self, account: AccountRef) -> None:
        """Delete the person's rows in `account.home`."""
        scope = TenancyScope(account.home, account.user_id)
        async with self._transactions.begin(scope) as session:
            await session.execute(delete(SESSIONS).where(SESSIONS.user_id == account.user_id))

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """The table, while it still holds the person's rows."""
        scope = TenancyScope(account.home, account.user_id)
        return await tables_holding(self._transactions, scope, [TABLE], account.user_id)
