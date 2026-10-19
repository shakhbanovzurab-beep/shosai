"""A person's folders of meetings (plan step 7b, MT-D7): flat, personal, coloured in turn.

A folder is named 1 to 40 characters and takes the next colour of the cabinet's cycle —
green, violet, red, blue, amber — by how many folders the person has. A create may carry an
`Idempotency-Key`: a retry answers the folder it made. Deleting a folder leaves its
meetings in no folder (the database sets their folder to null), never deletes them.
Folders are personal by nature: another person's folder is a 404.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Table, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.idempotency.ledger import (
    EffectKey,
    EffectLedger,
    EffectScope,
    account_key,
    fingerprint_of,
)
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.pagination.cursor import CursorCodec
from shosai.core.pagination.keyset import Keyset
from shosai.core.pagination.page import Page, PageRequest, page_of
from shosai.features.identity.contracts import Principal
from shosai.features.meetings.application.library import FolderNotFoundError
from shosai.features.meetings.domain.library import (
    FolderColor,
    LibraryRuleError,
    checked_folder_name,
    folder_color,
)
from shosai.features.meetings.infrastructure.notes_records import FolderRecord

FOLDER_CREATES: Final = EffectScope("meetings.folder_create", timedelta(hours=24))
FOLDERS: Final = cast("Table", FolderRecord.__table__)
FOLDER_ORDER: Final = Keyset((FOLDERS.c.created_at, FOLDERS.c.id))


class FolderPosition(BaseModel):
    """Where a page of folders ended."""

    created_at: datetime
    folder_id: UUID


FOLDERS_CURSOR: Final = CursorCodec("meetings.folders", FolderPosition)


class FolderCreate(BaseModel):
    """A folder to make; its print tells a retry from another request."""

    name: str


class FolderMade(BaseModel):
    """The folder a create made."""

    folder_id: UUID


@dataclass(frozen=True, slots=True)
class Folder:
    """A folder as its owner sees it."""

    folder_id: UUID
    name: str
    color: FolderColor
    created_at: datetime


def folder_of(record: FolderRecord) -> Folder:
    """A stored folder."""
    return Folder(record.id, record.name, FolderColor(record.color), record.created_at)


def checked_name(raw: str) -> str:
    """The folder's name, or 422 with the rule it breaks."""
    try:
        return checked_folder_name(raw)
    except LibraryRuleError as error:
        raise AppError(error.code, HTTPStatus.UNPROCESSABLE_ENTITY) from error


class Folders:
    """Lists, makes, renames and deletes a person's folders."""

    def __init__(
        self,
        transactions: HomeTransactions,
        effects: EffectLedger,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._effects = effects
        self._clock = clock

    async def page(self, principal: Principal, request: PageRequest) -> Page[Folder]:
        """A page of the person's folders, oldest first, as the cabinet lists them."""
        after = None
        if request.cursor is not None:
            position = FOLDERS_CURSOR.decode(request.cursor)
            after = (position.created_at, position.folder_id)
        statement = select(FolderRecord).where(FolderRecord.user_id == principal.user_id)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            rows = (await session.scalars(FOLDER_ORDER.page(statement, after, request.limit))).all()
        return page_of(
            [folder_of(row) for row in rows], request, FOLDERS_CURSOR, lambda f: f,
            lambda f: FolderPosition(created_at=f.created_at, folder_id=f.folder_id),
        )  # fmt: skip

    async def create(self, principal: Principal, name: str, client_key: str | None) -> Folder:
        """A new folder in the next colour; once per `Idempotency-Key` when one is sent."""
        clean = checked_name(name)
        async with self._transactions.begin(principal.scope()) as session:
            if client_key is None:
                made = await self._make(session, principal, clean)
            else:
                effect = EffectKey(
                    FOLDER_CREATES,
                    account_key(principal.user_id, client_key),
                    fingerprint_of(FolderCreate(name=clean)),
                )
                outcome = await self._effects.once(
                    session, effect, FolderMade, lambda: self._make(session, principal, clean)
                )
                made = outcome.outcome
            record = await session.get(FolderRecord, made.folder_id)
        if record is None:
            raise FolderNotFoundError
        return folder_of(record)

    async def _make(self, session: AsyncSession, principal: Principal, name: str) -> FolderMade:
        existing = await session.scalar(
            select(func.count())
            .select_from(FolderRecord)
            .where(FolderRecord.user_id == principal.user_id)
        )
        now = self._clock()
        record = FolderRecord(
            id=new_id(), user_id=principal.user_id, name=name,
            color=folder_color(int(existing or 0)).value, created_at=now, updated_at=now,
        )  # fmt: skip
        session.add(record)
        await session.flush()
        return FolderMade(folder_id=record.id)

    async def rename(self, principal: Principal, folder_id: UUID, name: str) -> Folder:
        """The folder under its new name."""
        clean = checked_name(name)
        async with self._transactions.begin(principal.scope()) as session:
            record = await self._own(session, principal, folder_id)
            record.name, record.updated_at = clean, self._clock()
            return folder_of(record)

    async def delete(self, principal: Principal, folder_id: UUID) -> None:
        """Delete the folder; its meetings stay, in no folder."""
        async with self._transactions.begin(principal.scope()) as session:
            await session.delete(await self._own(session, principal, folder_id))

    async def _own(
        self, session: AsyncSession, principal: Principal, folder_id: UUID
    ) -> FolderRecord:
        record = await session.get(FolderRecord, folder_id, with_for_update=True)
        if record is None or record.user_id != principal.user_id:
            raise FolderNotFoundError
        return record
