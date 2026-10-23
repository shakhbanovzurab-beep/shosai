"""The task routes the bench serves, every service on one clock the test may set (§3.9)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.ports.directory import PortDirectory
from shosai.features.tasks.application.attachments import Attachments
from shosai.features.tasks.application.board_reads import BoardReads
from shosai.features.tasks.application.board_stickers import BoardStickers
from shosai.features.tasks.application.boards import BoardWrites
from shosai.features.tasks.application.cards import Cards
from shosai.features.tasks.application.clocks import Clocks
from shosai.features.tasks.application.columns import Columns
from shosai.features.tasks.application.comments import Comments
from shosai.features.tasks.application.stickers import Stickers
from shosai.features.tasks.application.subtasks import Subtasks
from shosai.features.tasks.application.task_edits import TaskEdits
from shosai.features.tasks.application.task_reads import TaskReads
from shosai.features.tasks.application.task_writes import TaskWrites
from shosai.features.tasks.application.values import Values
from shosai.features.tasks.channels.http.attachments import build_attachments_router
from shosai.features.tasks.channels.http.board_parts import build_board_parts_router
from shosai.features.tasks.channels.http.boards import build_boards_router
from shosai.features.tasks.channels.http.clocks import build_clocks_router
from shosai.features.tasks.channels.http.stickers import (
    build_stickers_router,
    build_values_router,
)
from shosai.features.tasks.channels.http.tasks import build_tasks_router
from shosai.features.tasks.channels.http.threads import build_threads_router


@dataclass
class TestClock:
    """The services' clock: the real one until the test sets a moment, then that moment."""

    moment: datetime | None = None

    def __call__(self) -> datetime:
        return datetime.now(UTC) if self.moment is None else self.moment

    def at(self, moment: datetime) -> None:
        """Hold the clock at a moment."""
        self.moment = moment

    def later(self, minutes: int) -> None:
        """Move the held clock on."""
        self.moment = self() + timedelta(minutes=minutes)


def task_routers(
    transactions: HomeTransactions,
    ports: PortDirectory,
    events: tuple[EventOutbox, EffectLedger],
    clock: TestClock,
) -> tuple[APIRouter, ...]:
    """Every route of tasks over the slot's homes, its services on the test's clock."""
    outbox, effects = events
    edits = TaskEdits(transactions, ports, outbox, clock)
    services = (
        TaskReads(transactions, ports),
        TaskWrites(transactions, ports, events, clock),
        edits,
    )
    threads = (Subtasks(transactions, ports, clock), Comments(transactions, ports, effects, clock))
    boards = (
        BoardReads(transactions, ports, clock),
        BoardWrites(transactions, ports, outbox, clock),
    )
    cards = Cards(transactions, ports, (services[1], edits), clock)
    return (
        build_tasks_router(services, ports),
        build_threads_router(threads, ports),
        build_attachments_router(Attachments(transactions, ports, clock), ports),
        build_boards_router(boards, ports),
        build_board_parts_router((Columns(transactions, clock), cards), ports),
        build_stickers_router(
            (Stickers(transactions, clock), BoardStickers(transactions, clock)), ports
        ),
        build_values_router(Values(transactions, ports, clock), ports),
        build_clocks_router(Clocks(transactions, ports, clock), ports),
    )
