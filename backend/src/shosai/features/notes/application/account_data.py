"""The notes slice's handler of a person's data: meetings with their transcript, notes and links.

The person's rows are their meetings and everything under them, their runs, folders,
templates and setting, and their own notes on any meeting they read; a meeting of a
workspace stays with it (nfr-16). A transfer takes their notes on their own meetings only.
Rows with a person column go through core's helpers; the transcript goes meeting by
meeting. The transient objects of runs are reached only through their pointers: erasing
records them for deletion in the same transaction that removes their rows, and deletes
them after it. Export leaves out the share link's token: a secret, not the person's content.

An archived meeting's lines come from its object: export and digest read it, a copy puts
it in the other home's bucket, erasing names it for deletion with the meeting. Where a
meeting's lines live is not the person's content, so the pointer is neither exported nor
digested: a meeting archived on one side only still compares equal (step 20).
"""

import hashlib
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import ColumnElement, Table, and_, delete, select

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
from shosai.core.storage.copy import copy_object
from shosai.core.storage.port import MultipartUploads, ObjectStorage
from shosai.features.notes.domain.transcript_archive import archive_due
from shosai.features.notes.infrastructure.meeting_records import (
    MeetingRecord,
    ParticipantRecord,
    SpeakerRecord,
    TranscriptLineRecord,
)
from shosai.features.notes.infrastructure.notes_records import (
    FindingRecord,
    FolderRecord,
    NotesRecord,
    SettingsRecord,
    TemplateRecord,
)
from shosai.features.notes.infrastructure.own_notes_records import OwnNotesRecord
from shosai.features.notes.infrastructure.run_objects import (
    RunObjects,
    record_deletions,
    run_keys,
)
from shosai.features.notes.infrastructure.run_records import RunRecord
from shosai.features.notes.infrastructure.share_records import (
    ShareCommentRecord,
    ShareLinkRecord,
)
from shosai.features.notes.infrastructure.transcript_archive import TranscriptArchive
from shosai.features.notes.infrastructure.transcript_rows import (
    copy_archives,
    copy_transcripts,
    person_meetings,
    transcript_lines,
)

OWNER: Final = "notes"
# В порядке ссылок: папки раньше встреч, встречи раньше их строк, ссылка раньше комментариев.
PERSON_MODELS: Final = (
    FolderRecord,
    TemplateRecord,
    SettingsRecord,
    MeetingRecord,
    SpeakerRecord,
    ParticipantRecord,
    NotesRecord,
    OwnNotesRecord,
    FindingRecord,
    RunRecord,
    ShareLinkRecord,
    ShareCommentRecord,
)
PERSONAL_MODELS: Final = (FolderRecord, TemplateRecord, SettingsRecord, OwnNotesRecord)
ACCOUNT_DATA: Final = AccountDataSpec(
    OWNER,
    tuple(
        TableCoverage(model.__tablename__, Treatment.ERASE)
        for model in (*PERSON_MODELS, TranscriptLineRecord)
    ),
)
POINTER: Final = ("transcript_archive_key", "transcript_archive_lines")
KEYS: Final = {
    SettingsRecord: "user_id",
    NotesRecord: "session_id",
    ShareLinkRecord: "session_id",
}


def personal_meetings(user_id: UUID) -> ColumnElement[bool]:
    """The predicate of the person's own meetings, not a workspace's."""
    return and_(MeetingRecord.user_id == user_id, MeetingRecord.org_id.is_(None))


def notes_that_move(user_id: UUID) -> ColumnElement[bool]:
    """The person's own notes on their own meetings: the ones a transfer takes along.

    Notes on someone else's meeting stay where that meeting is, so they are exported and
    erased with the person, never copied to the other home.
    """
    return OwnNotesRecord.session_id.in_(select(MeetingRecord.id).where(personal_meetings(user_id)))


def _copied(model: type[ModelBase]) -> PersonRows:
    rows = whole_rows(cast("Table", model.__table__), KEYS.get(model, "id"))
    return replace(rows, only=notes_that_move) if model is OwnNotesRecord else rows


COPIED: Final = tuple(_copied(model) for model in PERSON_MODELS)


def _without(rows: PersonRows, left_out: tuple[str, ...]) -> PersonRows:
    return replace(rows, columns=tuple(name for name in rows.columns if name not in left_out))


def _digested(rows: PersonRows) -> PersonRows:
    return _without(rows, POINTER) if rows.table.name == MeetingRecord.__tablename__ else rows


def _exported(rows: PersonRows) -> PersonRows:
    if rows.table.name == OwnNotesRecord.__tablename__:
        return replace(rows, only=None)
    if rows.table.name == ShareLinkRecord.__tablename__:
        return PersonRows(rows.table, _without(rows, ("token",)).columns, rows.key)
    return _digested(rows)


DIGESTED: Final = tuple(_digested(rows) for rows in COPIED)
EXPORTED: Final = tuple(_exported(rows) for rows in COPIED)


class NotesAccountData:
    """The `core.account_data_handlers` binding of meetings."""

    def __init__(
        self,
        transactions: HomeTransactions,
        storage: tuple[Mapping[Home, ObjectStorage], Mapping[Home, MultipartUploads]],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._objects, self._uploads = storage
        self._archive = TranscriptArchive(self._objects)
        self._clock = clock

    @property
    def owner(self) -> str:
        """The slice's declaration."""
        return OWNER

    async def export(self, account: AccountRef) -> AsyncIterator[ExportFile]:
        """The rows of every table, then the transcript meeting by meeting."""
        scope = TenancyScope(account.home, account.user_id)
        for rows in EXPORTED:
            lines = person_lines(self._transactions, scope, rows, account.user_id)
            yield ExportFile(f"{rows.table.name}.jsonl", lines)
        meetings = await person_meetings(self._transactions, scope, account.user_id)
        lines = transcript_lines(self._transactions, self._archive, scope, meetings)
        yield ExportFile("transcript_segments.jsonl", lines)

    async def erase(self, account: AccountRef) -> None:
        """Delete the person's meetings and rows, then their transient objects."""
        await self.purge(account)

    async def copy(self, account: AccountRef, to_home: Home) -> None:
        """The rows and lines to the other home, then every transient object under its key."""
        homes = (account.home, to_home)
        for rows in COPIED:
            await copy_person_rows(self._transactions, rows, account.user_id, homes)
        scope = TenancyScope(account.home, account.user_id)
        meetings = await person_meetings(self._transactions, scope, account.user_id)
        now = self._clock()
        archived = [m for m in meetings if m.archive or archive_due(m.started_at, now)]
        stored = [m.id for m in meetings if m not in archived]
        await copy_transcripts(self._transactions, account.user_id, stored, homes)
        await copy_archives(self._transactions, self._archive, (account.user_id, archived), homes)
        for key in await self._keys(account):
            await copy_object(self._objects[account.home], self._uploads[to_home], key)

    async def manifest(self, account: AccountRef) -> Mapping[str, str]:
        """A digest of each table and of the transcript, and of every named object."""
        scope = TenancyScope(account.home, account.user_id)
        digests = {
            rows.table.name: await person_digest(self._transactions, scope, rows, account.user_id)
            for rows in DIGESTED
        }
        meetings = await person_meetings(self._transactions, scope, account.user_id)
        lines = hashlib.sha256()
        async for chunk in transcript_lines(self._transactions, self._archive, scope, meetings):
            lines.update(chunk)
        digests["transcript_segments"] = lines.hexdigest()
        listing = hashlib.sha256()
        storage = self._objects[account.home]
        for key in await self._keys(account):
            info = await storage.head(key)
            listing.update(f"{key}:{None if info is None else info.size}\n".encode())
        digests["objects"] = listing.hexdigest()
        return digests

    async def purge(self, account: AccountRef) -> None:
        """The person's rows in `account.home`, meeting by meeting, then their objects."""
        scope = TenancyScope(account.home, account.user_id)
        meetings = await person_meetings(self._transactions, scope, account.user_id)
        for meeting in meetings:
            async with self._transactions.begin(scope) as session:
                keys = await run_keys(session, RunRecord.session_id == meeting.id)
                # Ключ архива берётся из удалённой строки: архиватор мог успеть после списка.
                archived = await session.scalar(
                    delete(MeetingRecord)
                    .where(MeetingRecord.id == meeting.id, personal_meetings(account.user_id))
                    .returning(MeetingRecord.transcript_archive_key)
                )
                keys = sorted({*keys, archived}) if archived else keys
                await record_deletions(session, keys)
            await self._delete_objects(account.home, keys)
        async with self._transactions.begin(scope) as session:
            for model in PERSONAL_MODELS:
                await session.execute(delete(model).where(model.user_id == account.user_id))

    async def remains(self, account: AccountRef) -> tuple[str, ...]:
        """The tables still holding the person's rows.

        Every row under a meeting goes with it, so a person's own meetings answer for them;
        a workspace's meeting is the workspace's and is not a remain.
        """
        scope = TenancyScope(account.home, account.user_id)
        tables = [cast("Table", model.__table__) for model in PERSONAL_MODELS]
        found = list(await tables_holding(self._transactions, scope, tables, account.user_id))
        async with self._transactions.begin(scope, read_only=True) as session:
            left = await session.scalar(
                select(MeetingRecord.id).where(personal_meetings(account.user_id)).limit(1)
            )
        if left is not None:
            found.append(MeetingRecord.__tablename__)
        return tuple(found)

    async def _keys(self, account: AccountRef) -> list[str]:
        """Every transient object the person's runs name, each once."""
        scope = TenancyScope(account.home, account.user_id)
        async with self._transactions.begin(scope, read_only=True) as session:
            return await run_keys(session, RunRecord.user_id == account.user_id)

    async def _delete_objects(self, home: Home, keys: list[str]) -> None:
        await RunObjects(self._transactions, self._objects).delete(home, keys)
