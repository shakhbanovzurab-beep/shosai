"""A task's comments (tasks plan §3.3, §3.8, §3.12; KG-D2).

Whoever may read a task may read and write its comments (TK-D2); only the author edits or
deletes one. Comments are plain text of up to 5 000 characters, paged newest first by an
opaque cursor on the last one shown, so a comment written meanwhile repeats nothing. A new
comment is made once per `Idempotency-Key`. A Jira task has no comments (KG-D8). A new or
deleted comment changes the card's count, so it raises the revision of the reader's board;
an edit does not. A person's comment on a meeting's task touches the meeting's set.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Final, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Table, select
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
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, Principal
from shosai.features.tasks.application.scoping import (
    Scoping,
    locked_task,
    raise_revisions,
    rule_failure,
    touch_sets,
)
from shosai.features.tasks.domain.tasks import TaskRuleError, TaskSource, checked_comment
from shosai.features.tasks.infrastructure.task_records import TaskRecord
from shosai.features.tasks.infrastructure.thread_records import TaskCommentRecord

COMMENT_CREATES: Final = EffectScope("tasks.comment_create", timedelta(hours=24))
COMMENTS: Final = cast("Table", TaskCommentRecord.__table__)
NEWEST: Final = Keyset((COMMENTS.c.id,), descending=True)


class CommentPosition(BaseModel):
    """Where a page of comments stopped: the last comment shown."""

    id: UUID


CURSORS: Final = CursorCodec("tasks.comments", CommentPosition)


class CommentMade(BaseModel):
    """The outcome a repeated `Idempotency-Key` answers with."""

    comment_id: UUID


class CommentPrint(BaseModel):
    """What a key's request is compared by."""

    task_id: UUID
    body: str


@dataclass(frozen=True, slots=True)
class CommentView:
    """A comment as the reader sees it."""

    id: UUID
    author_user_id: UUID
    author_name: str
    is_you: bool
    body: str
    created_at: datetime
    edited_at: datetime | None


class Comments:
    """Pages, writes, edits and deletes the comments of tasks."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        effects: EffectLedger,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._effects = effects
        self._clock = clock
        self._scoping = Scoping(transactions, ports)

    async def page(
        self, principal: Principal, task_id: UUID, request: PageRequest
    ) -> Page[CommentView]:
        """A page of the task's comments, newest first."""
        after = None if request.cursor is None else (CURSORS.decode(request.cursor).id,)
        async with self._transactions.begin(principal.scope(), read_only=True) as session:
            await locked_task(session, self._ports, principal.user_id, task_id, lock=False)
            statement = select(TaskCommentRecord).where(TaskCommentRecord.task_id == task_id)
            rows = list(await session.scalars(NEWEST.page(statement, after, request.limit)))
            names = await self._names(session, rows)
        return page_of(
            rows,
            request,
            CURSORS,
            lambda row: _view(row, principal.user_id, names),
            lambda row: CommentPosition(id=row.id),
        )

    async def create(
        self, principal: Principal, task_id: UUID, body: str, client_key: str | None
    ) -> CommentView:
        """A new comment by the person; once per key when one is sent."""
        clean = _body(body)
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            task = await locked_task(session, self._ports, principal.user_id, task_id, lock=False)
            if task.source == TaskSource.JIRA.value:
                raise AppError("jira_unsupported", HTTPStatus.CONFLICT)
            if client_key is None:
                comment_id = await self._write(session, principal.user_id, task, clean)
            else:
                effect = EffectKey(
                    COMMENT_CREATES,
                    account_key(principal.user_id, client_key),
                    fingerprint_of(CommentPrint(task_id=task_id, body=clean)),
                )

                async def write() -> CommentMade:
                    made = await self._write(session, principal.user_id, task, clean)
                    return CommentMade(comment_id=made)

                done = await self._effects.once(session, effect, CommentMade, write)
                comment_id = done.outcome.comment_id
            return await self._read(session, principal.user_id, task_id, comment_id)

    async def edit(
        self, principal: Principal, task_id: UUID, comment_id: UUID, body: str
    ) -> CommentView:
        """The author's comment with its new text."""
        clean = _body(body)
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            await locked_task(session, self._ports, principal.user_id, task_id, lock=False)
            comment = await _own(session, principal.user_id, task_id, comment_id)
            comment.body = clean
            comment.edited_at = self._clock()
            await session.flush()
            return await self._read(session, principal.user_id, task_id, comment_id)

    async def delete(self, principal: Principal, task_id: UUID, comment_id: UUID) -> None:
        """Remove the author's comment."""
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            task = await locked_task(session, self._ports, principal.user_id, task_id, lock=False)
            await session.delete(await _own(session, principal.user_id, task_id, comment_id))
            await self._touched(session, principal.user_id, task, self._clock())

    async def _write(
        self, session: AsyncSession, author: UUID, task: TaskRecord, body: str
    ) -> UUID:
        now = self._clock()
        comment = TaskCommentRecord(
            id=new_id(),
            task_id=task.id,
            user_id=task.user_id,
            org_id=task.org_id,
            author_user_id=author,
            body=body,
            created_at=now,
        )
        session.add(comment)
        await self._touched(session, author, task, now)
        return comment.id

    async def _touched(
        self, session: AsyncSession, viewer: UUID, task: TaskRecord, now: datetime
    ) -> None:
        await session.flush()
        if task.source_meeting_id is not None:
            await touch_sets(session, [task.source_meeting_id], now)
        await raise_revisions(session, viewer, [task.id], now)

    async def _read(
        self, session: AsyncSession, viewer: UUID, task_id: UUID, comment_id: UUID
    ) -> CommentView:
        comment = await session.scalar(
            select(TaskCommentRecord).where(
                TaskCommentRecord.id == comment_id, TaskCommentRecord.task_id == task_id
            )
        )
        if comment is None:
            raise AppError("comment_not_found", HTTPStatus.NOT_FOUND)
        return _view(comment, viewer, await self._names(session, [comment]))

    async def _names(
        self, session: AsyncSession, rows: list[TaskCommentRecord]
    ) -> Mapping[UUID, str]:
        authors = {row.author_user_id for row in rows}
        if not authors:
            return {}
        return await self._ports.get(ACCOUNT_PROFILE_READER).names(session, authors)


async def _own(
    session: AsyncSession, viewer: UUID, task_id: UUID, comment_id: UUID
) -> TaskCommentRecord:
    """The task's comment, if the person wrote it."""
    comment = await session.scalar(
        select(TaskCommentRecord)
        .where(TaskCommentRecord.id == comment_id, TaskCommentRecord.task_id == task_id)
        .with_for_update()
    )
    if comment is None:
        raise AppError("comment_not_found", HTTPStatus.NOT_FOUND)
    if comment.author_user_id != viewer:
        raise AppError("not_comment_author", HTTPStatus.FORBIDDEN)
    return comment


def _body(raw: str) -> str:
    try:
        return checked_comment(raw)
    except TaskRuleError as error:
        raise rule_failure(error) from error


def _view(row: TaskCommentRecord, viewer: UUID, names: Mapping[UUID, str]) -> CommentView:
    return CommentView(
        id=row.id,
        author_user_id=row.author_user_id,
        author_name=names.get(row.author_user_id, ""),
        is_you=row.author_user_id == viewer,
        body=row.body,
        created_at=row.created_at,
        edited_at=row.edited_at,
    )
