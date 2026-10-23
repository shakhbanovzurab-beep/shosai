"""A task's stopwatch and timer, worked by whoever may change the task (tasks plan §3.9).

Each action takes the task's row lock in the task's space and answers the three time fields
with the server's moment, the one the action happened at (KT-D6). A start while running and
a stop while stopped change nothing; a start opens its span in the task's column on the
reader's board, unplaced when it sits on none; a reset clears the spans. The timer is set
anew from now, paused and resumed — a repeat changes nothing, and with no timer it is
`timer_not_set` — and removed. A Jira task has no clocks (KG-D8). An action raises the
revision of the reader's board, as the cabinet's mocks do; it is not a change of the task's
fields, so its change time, version and events stay (KT-D8).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal
from shosai.features.tasks.application import clock_rules
from shosai.features.tasks.application.clock_views import clocks_of
from shosai.features.tasks.application.scoping import Scoping, locked_task, raise_revisions
from shosai.features.tasks.domain.clocks import TaskClocks, Timer, at_ms, held, timer_from
from shosai.features.tasks.domain.tasks import TaskSource, TaskStatus
from shosai.features.tasks.infrastructure.task_records import TaskRecord

type Act = Callable[[AsyncSession, UUID, TaskRecord, datetime], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ClocksView:
    """A task's time fields and the moment the server answered."""

    clocks: TaskClocks
    server_now: datetime


def timer_not_set() -> AppError:
    """A pause or a resume of a task without a timer."""
    return AppError("timer_not_set", HTTPStatus.CONFLICT)


class Clocks:
    """Starts, stops and resets a task's stopwatch; sets, holds and removes its timer."""

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

    async def start(self, principal: Principal, task_id: UUID) -> ClocksView:
        """The stopwatch running, in the task's column on the reader's board."""
        return await self._act(principal, task_id, _start)

    async def stop(self, principal: Principal, task_id: UUID) -> ClocksView:
        """The stopwatch stopped."""
        return await self._act(principal, task_id, _stop)

    async def reset(self, principal: Principal, task_id: UUID) -> ClocksView:
        """The stopwatch cleared."""
        return await self._act(principal, task_id, _reset)

    async def set_timer(self, principal: Principal, task_id: UUID, length_ms: int) -> ClocksView:
        """The timer set anew: the whole length from now."""

        async def set_anew(_: AsyncSession, __: UUID, task: TaskRecord, now: datetime) -> None:
            _write_timer(task, timer_from(length_ms, now))

        return await self._act(principal, task_id, set_anew)

    async def hold_timer(self, principal: Principal, task_id: UUID, *, paused: bool) -> ClocksView:
        """The timer paused or going on again."""

        async def hold(_: AsyncSession, __: UUID, task: TaskRecord, now: datetime) -> None:
            if task.timer_length_ms is None:
                raise timer_not_set()
            current = Timer(task.timer_length_ms, task.timer_ends_at, task.timer_paused_left_ms)
            _write_timer(task, held(current, paused=paused, now=now))

        return await self._act(principal, task_id, hold)

    async def clear_timer(self, principal: Principal, task_id: UUID) -> ClocksView:
        """The timer removed."""
        return await self._act(principal, task_id, _clear_timer)

    async def _act(self, principal: Principal, task_id: UUID, act: Act) -> ClocksView:
        viewer, now = principal.user_id, at_ms(self._clock())
        scope = await self._scoping.space_of(principal, task_id)
        async with self._transactions.begin(scope) as session:
            task = await locked_task(session, self._ports, viewer, task_id)
            if task.source == TaskSource.JIRA.value:
                raise AppError("jira_unsupported", HTTPStatus.CONFLICT)
            await act(session, viewer, task, now)
            await session.flush()
            await raise_revisions(session, viewer, [task_id], now)
        return ClocksView(clocks_of(task), now)


async def _start(session: AsyncSession, viewer: UUID, task: TaskRecord, now: datetime) -> None:
    spot = await clock_rules.shown_in(session, viewer, task.id, TaskStatus(task.status))
    await clock_rules.start(session, task, None if spot is None else spot[1], now)


async def _stop(session: AsyncSession, _: UUID, task: TaskRecord, now: datetime) -> None:
    await clock_rules.stop(session, task, now)


async def _reset(session: AsyncSession, _: UUID, task: TaskRecord, __: datetime) -> None:
    await clock_rules.reset(session, task)


async def _clear_timer(_: AsyncSession, __: UUID, task: TaskRecord, ___: datetime) -> None:
    _write_timer(task, None)


def _write_timer(task: TaskRecord, timer: Timer | None) -> None:
    task.timer_length_ms = None if timer is None else timer.length_ms
    task.timer_ends_at = None if timer is None else timer.ends_at
    task.timer_paused_left_ms = None if timer is None else timer.paused_left_ms
