"""Meetings' handler of a person's data: their personal rooms and what each room keeps.

A person's rows are the rooms they opened in Personal, with their calls, bans, the chat of a
call still open, their recordings' rows and their boards. A room opened in a workspace is
the workspace's (nfr-16): it is neither exported nor moved with the person, and the
workspace's own declaration covers it. Erasing deletes the person's personal rooms, and what
hangs on them goes by the database's cascades; a repeat deletes nothing more. A recording's
file is File Manager's, erased by files.
"""

from collections.abc import AsyncIterator, Mapping
from typing import Final, cast
from uuid import UUID

from sqlalchemy import ColumnElement, Table, and_, delete, exists, select

from shosai.core.account_data.handlers import AccountRef, ExportFile
from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.db.model_base import ModelBase
from shosai.core.db.person_rows import (
    PersonRows,
    copy_person_rows,
    person_digest,
    person_lines,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.meetings.infrastructure.call_records import (
    RoomChatMessageRecord,
    RoomRecordingRecord,
    RoomWhiteboardRecord,
)
from shosai.features.meetings.infrastructure.room_records import (
    RoomBanRecord,
    RoomCallRecord,
    RoomRecord,
)

OWNER: Final = "meetings"
OWNER_COLUMN: Final = "owner_id"
# В порядке ссылок: комнаты раньше звонков, звонки раньше чата.
MODELS: Final[tuple[type[ModelBase], ...]] = (
    RoomRecord,
    RoomCallRecord,
    RoomBanRecord,
    RoomChatMessageRecord,
    RoomRecordingRecord,
    RoomWhiteboardRecord,
)
KEYS: Final[Mapping[type[ModelBase], str]] = {
    RoomRecord: "id",
    RoomCallRecord: "id",
    RoomBanRecord: "id",
    RoomChatMessageRecord: "id",
    RoomRecordingRecord: "id",
    RoomWhiteboardRecord: "room_id",
}
ACCOUNT_DATA: Final = AccountDataSpec(
    OWNER, tuple(TableCoverage(model.__tablename__, Treatment.ERASE) for model in MODELS)
)


def _table(model: type[ModelBase]) -> Table:
    return cast("Table", model.__table__)


def _personal(model: type[ModelBase]) -> PersonRows:
    table = _table(model)

    def personal(_user_id: UUID) -> ColumnElement[bool]:
        return table.c.org_id.is_(None)

    return PersonRows(
        table=table,
        columns=tuple(table.columns.keys()),
        key=KEYS[model],
        person=OWNER_COLUMN,
        only=personal,
    )


PERSONAL_ROWS: Final = tuple(_personal(model) for model in MODELS)


class MeetingsAccountData:
    """The `core.account_data_handlers` binding of meetings."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    @property
    def owner(self) -> str:
        """The slice's declaration."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """One JSON Lines file per table of the person's personal rooms and what they keep."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in PERSONAL_ROWS:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)

    async def erase(self, account: AccountRef) -> None:
        """Delete the person's personal rooms; their calls, chat and the rest go with them."""
        await self.purge(account)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """Copy the person's personal rooms and what they keep to the other home."""
        for rows in PERSONAL_ROWS:
            await copy_person_rows(
                self._transactions, rows, account.user_id, (account.home, to_home)
            )

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of each table's personal rows of the person in `account.home`."""
        scope = TenancyScope(account.home, account.user_id)
        return {
            rows.table.name: await person_digest(self._transactions, scope, rows, account.user_id)
            for rows in PERSONAL_ROWS
        }

    async def purge(self, account: AccountRef) -> None:
        """Delete the person's personal rooms in `account.home`; the rest goes by cascade."""
        rooms = _table(RoomRecord)
        async with self._transactions.begin(TenancyScope(account.home, account.user_id)) as session:
            await session.execute(
                delete(rooms).where(rooms.c.owner_id == account.user_id, rooms.c.org_id.is_(None))
            )

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """The tables still holding personal rows of the person, in one round trip."""
        tables = [_table(model) for model in MODELS]
        checks = [
            exists()
            .where(and_(table.c.owner_id == account.user_id, table.c.org_id.is_(None)))
            .label(table.name)
            for table in tables
        ]
        scope = TenancyScope(account.home, account.user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            found = (await session.execute(select(*checks))).one()
        return tuple(table.name for table, holds in zip(tables, found, strict=True) if holds)
