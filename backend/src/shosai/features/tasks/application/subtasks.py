"""A task's checklist (tasks plan §3.3, §3.8, §3.12; KG-D2).

Whoever may read a task may change its checklist (TK-D2). A task holds at most 100 lines,
checked under the task's row lock, so two people adding at once cannot pass the limit. A
line goes to its position among the others, the end by default, past the end at the end;
its order is a fractional key, so a move writes one row, and a key grown too long respaces
the list. A Jira task has no checklist (KG-D8). Every change moves the task's change time,
touches the set of a meeting's task and raises the revision of the reader's board.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.ids import new_id
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application.scoping import (
    Scoping,
    locked_task,
    rule_failure,
    task_changed,
)
from shosai.features.tasks.application.task_parts import SubtaskView
from shosai.features.tasks.domain.ranks import needs_rebalance, rank_at, spaced_ranks
from shosai.features.tasks.domain.tasks import TaskRuleError, TaskSource, checked_title
from shosai.features.tasks.infrastructure.thread_records import TaskSubtaskRecord

SUBTASKS_MAX: Final = 100


@dataclass(frozen=True, slots=True)
class SubtaskChange:
    """What a change of a line sets; None leaves a field as it is."""

    title: str | None = None
    done: bool | None = None
    position: int | None = None


class Subtasks:
    """Adds, changes and removes the lines of a task's checklist."""

    def __init__(
        self,
        transactions: HomeTransactions,
        ports: PortDirectory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transactions = transactions
        self._ports = ports
        self._clock = clock
        self._scoping = Scoping(transactions, ports)

    async def create(
        self, principal: Principal, task_id: UUID, title: str, position: int | None
    ) -> SubtaskView:
        """A new line at its position, the end by default."""
        clean = _title(title)
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            task = await locked_task(session, self._ports, principal.user_id, task_id)
            if task.source == TaskSource.JIRA.value:
                raise AppError("jira_unsupported", HTTPStatus.CONFLICT)
            lines = await _lines(session, task_id)
            if len(lines) >= SUBTASKS_MAX:
                raise AppError("subtasks_full", HTTPStatus.CONFLICT)
            now = self._clock()
            line = TaskSubtaskRecord(
                id=new_id(),
                task_id=task_id,
                user_id=task.user_id,
                org_id=task.org_id,
                title=clean,
                done=False,
                rank="",
                created_at=now,
                updated_at=now,
            )
            _put(lines, line, len(lines) if position is None else position)
            session.add(line)
            await task_changed(session, principal.user_id, task, now)
            return _view(line)

    async def change(
        self, principal: Principal, task_id: UUID, subtask_id: UUID, change: SubtaskChange
    ) -> SubtaskView:
        """The line after its change."""
        clean = None if change.title is None else _title(change.title)
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            task = await locked_task(session, self._ports, principal.user_id, task_id)
            lines = await _lines(session, task_id)
            line = next((found for found in lines if found.id == subtask_id), None)
            if line is None:
                raise AppError("subtask_not_found", HTTPStatus.NOT_FOUND)
            now = self._clock()
            if clean is not None:
                line.title = clean
            if change.done is not None:
                line.done = change.done
            if change.position is not None:
                lines.remove(line)
                _put(lines, line, change.position)
            line.updated_at = now
            await task_changed(session, principal.user_id, task, now)
            return _view(line)

    async def delete(self, principal: Principal, task_id: UUID, subtask_id: UUID) -> None:
        """Remove the line."""
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            task = await locked_task(session, self._ports, principal.user_id, task_id)
            line = await session.scalar(
                select(TaskSubtaskRecord).where(
                    TaskSubtaskRecord.id == subtask_id, TaskSubtaskRecord.task_id == task_id
                )
            )
            if line is None:
                raise AppError("subtask_not_found", HTTPStatus.NOT_FOUND)
            await session.delete(line)
            await task_changed(session, principal.user_id, task, self._clock())


def _title(raw: str) -> str:
    try:
        return checked_title(raw)
    except TaskRuleError as error:
        raise rule_failure(error) from error


async def _lines(session: AsyncSession, task_id: UUID) -> list[TaskSubtaskRecord]:
    """The task's lines in their order."""
    found = await session.scalars(
        select(TaskSubtaskRecord)
        .where(TaskSubtaskRecord.task_id == task_id)
        .order_by(TaskSubtaskRecord.rank)
    )
    return list(found)


def _put(lines: list[TaskSubtaskRecord], line: TaskSubtaskRecord, position: int) -> None:
    """Give the line the key of its position among the others; respace a grown list."""
    line.rank = rank_at([other.rank for other in lines], position)
    if needs_rebalance(line.rank):
        index = min(max(position, 0), len(lines))
        ordered = [*lines[:index], line, *lines[index:]]
        for other, rank in zip(ordered, spaced_ranks(len(ordered)), strict=True):
            other.rank = rank


def _view(line: TaskSubtaskRecord) -> SubtaskView:
    return SubtaskView(line.id, line.title, line.done)
