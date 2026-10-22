"""Tasks' handler of a person's data: personal tasks, boards, their columns and placements.

The person's rows are their personal tasks and the sets of their personal meetings, their
boards with columns, where tasks sit on them, and their settings. A workspace's task stays
with the workspace, whoever made it (nfr-16): it is neither exported nor erased with the
person, and the workspace passes it to a successor when the member goes (step 6). The
person's placements of a workspace's tasks are their own rows: exported and erased with
them, never copied to another home, where those tasks are not. Erasing deletes boards and
personal tasks, and their placements, columns and settings go with them by the database's
cascades; a repeat deletes nothing more.
"""

from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import replace
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
    tables_holding,
    whole_rows,
)
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
    TaskSettingsRecord,
)
from shosai.features.tasks.infrastructure.task_records import MeetingTaskSetRecord, TaskRecord

OWNER: Final = "tasks"
# В порядке ссылок: задачи и доски раньше колонок и мест, доски раньше настроек.
MODELS: Final = (
    TaskRecord,
    MeetingTaskSetRecord,
    BoardRecord,
    BoardColumnRecord,
    TaskPlacementRecord,
    TaskSettingsRecord,
)
PERSONAL_MODELS: Final = (BoardRecord, BoardColumnRecord, TaskPlacementRecord, TaskSettingsRecord)
ACCOUNT_DATA: Final = AccountDataSpec(
    OWNER, tuple(TableCoverage(model.__tablename__, Treatment.ERASE) for model in MODELS)
)
KEYS: Final[Mapping[type[ModelBase], str]] = {
    MeetingTaskSetRecord: "meeting_id",
    TaskPlacementRecord: "task_id",
    TaskSettingsRecord: "user_id",
}


def personal_tasks(user_id: UUID) -> ColumnElement[bool]:
    """The person's own tasks, not a workspace's."""
    return and_(TaskRecord.user_id == user_id, TaskRecord.org_id.is_(None))


def _personal_sets(_user_id: UUID) -> ColumnElement[bool]:
    return MeetingTaskSetRecord.org_id.is_(None)


def _personal_tasks_only(_user_id: UUID) -> ColumnElement[bool]:
    return TaskRecord.org_id.is_(None)


def _placements_of_personal_tasks(user_id: UUID) -> ColumnElement[bool]:
    return TaskPlacementRecord.task_id.in_(select(TaskRecord.id).where(personal_tasks(user_id)))


NARROWED: Final[Mapping[type[ModelBase], Callable[[UUID], ColumnElement[bool]]]] = {
    TaskRecord: _personal_tasks_only,
    MeetingTaskSetRecord: _personal_sets,
}


# Таблицы с отложенным уникальным порядком: копия пропускает уже перенесённые по первичному ключу.
ARBITERS: Final[Mapping[type[ModelBase], tuple[str, ...]]] = {
    BoardColumnRecord: ("id",),
    TaskPlacementRecord: ("user_id", "task_id"),
}


def _rows(model: type[ModelBase]) -> PersonRows:
    rows = whole_rows(cast("Table", model.__table__), KEYS.get(model, "id"))
    rows = replace(rows, arbiter=ARBITERS.get(model, ()))
    only = NARROWED.get(model)
    return rows if only is None else replace(rows, only=only)


EXPORTED: Final = tuple(_rows(model) for model in MODELS)
# Переезжают только личные задачи, поэтому и места — только у них.
COPIED: Final = tuple(
    replace(rows, only=_placements_of_personal_tasks)
    if rows.table.name == TaskPlacementRecord.__tablename__
    else rows
    for rows in EXPORTED
)


class TasksAccountData:
    """The `core.account_data_handlers` binding of tasks."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    @property
    def owner(self) -> str:
        """The slice's declaration."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """One JSON Lines file per table."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in EXPORTED:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)

    async def erase(self, account: AccountRef) -> None:
        """Delete the person's boards, personal tasks and sets in their home."""
        await self.purge(account)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """Copy the rows that move with the person to the other home, in reference order."""
        for rows in COPIED:
            await copy_person_rows(
                self._transactions, rows, account.user_id, (account.home, to_home)
            )

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of each table's moving rows in the person's home."""
        scope = TenancyScope(account.home, account.user_id)
        return {
            rows.table.name: await person_digest(self._transactions, scope, rows, account.user_id)
            for rows in COPIED
        }

    async def purge(self, account: AccountRef) -> None:
        """Delete the person's rows in `account.home`; a workspace's tasks stay."""
        user_id = account.user_id
        async with self._transactions.begin(TenancyScope(account.home, user_id)) as session:
            await session.execute(
                delete(TaskSettingsRecord).where(TaskSettingsRecord.user_id == user_id)
            )
            await session.execute(delete(BoardRecord).where(BoardRecord.user_id == user_id))
            await session.execute(
                delete(TaskPlacementRecord).where(TaskPlacementRecord.user_id == user_id)
            )
            await session.execute(delete(TaskRecord).where(personal_tasks(user_id)))
            await session.execute(
                delete(MeetingTaskSetRecord).where(
                    MeetingTaskSetRecord.user_id == user_id, MeetingTaskSetRecord.org_id.is_(None)
                )
            )

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """The tables still holding the person's rows; a workspace's tasks are not remains."""
        scope = TenancyScope(account.home, account.user_id)
        tables = [cast("Table", model.__table__) for model in PERSONAL_MODELS]
        found = list(await tables_holding(self._transactions, scope, tables, account.user_id))
        user_id = account.user_id
        async with self._transactions.begin(scope, read_only=True) as session:
            tasks_left, sets_left = (
                await session.execute(
                    select(
                        exists().where(personal_tasks(user_id)),
                        exists().where(
                            MeetingTaskSetRecord.user_id == user_id,
                            MeetingTaskSetRecord.org_id.is_(None),
                        ),
                    )
                )
            ).one()
        if tasks_left:
            found.append(TaskRecord.__tablename__)
        if sets_left:
            found.append(MeetingTaskSetRecord.__tablename__)
        return tuple(found)
