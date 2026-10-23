"""The one task API over the slot's homes: its routes, people's tokens, seeded tasks and boards.

People sign in with the test's bearer; identity's profile reader is replaced by names and
zones the test sets. Workspaces are written with the isolation kit's world. Every request
runs in the EU home unless a test names another.
"""

import uuid
from collections.abc import AsyncIterator, Collection, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

import httpx
import pytest_asyncio
from prometheus_client import CollectorRegistry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.records import OutboxMessage
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import ENTITLEMENTS
from shosai.features.files.contracts.held_objects import HELD_OBJECTS
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER, AUTHENTICATOR, AccountProfile
from shosai.features.notes.application.meeting_reader import MeetingsFindings, MeetingsReader
from shosai.features.notes.contracts import MEETING_FINDINGS, MEETING_READER
from shosai.features.notes.infrastructure.meeting_records import MEETING_RESOURCE
from shosai.features.notes.module import NOTES
from shosai.features.tasks.application.attachments import Attachments
from shosai.features.tasks.application.board_reads import BoardReads
from shosai.features.tasks.application.board_stickers import BoardStickers
from shosai.features.tasks.application.boards import BoardWrites
from shosai.features.tasks.application.cards import Cards
from shosai.features.tasks.application.columns import Columns
from shosai.features.tasks.application.comments import Comments
from shosai.features.tasks.application.placements import CardSpot, place
from shosai.features.tasks.application.stickers import Stickers
from shosai.features.tasks.application.subtasks import Subtasks
from shosai.features.tasks.application.task_edits import TaskEdits
from shosai.features.tasks.application.task_reads import TaskReads
from shosai.features.tasks.application.task_writes import TaskWrites
from shosai.features.tasks.application.values import Values
from shosai.features.tasks.channels.http.attachments import build_attachments_router
from shosai.features.tasks.channels.http.board_parts import build_board_parts_router
from shosai.features.tasks.channels.http.boards import build_boards_router
from shosai.features.tasks.channels.http.stickers import (
    build_stickers_router,
    build_values_router,
)
from shosai.features.tasks.channels.http.tasks import build_tasks_router
from shosai.features.tasks.channels.http.threads import build_threads_router
from shosai.features.tasks.infrastructure.board_records import (
    BoardColumnRecord,
    BoardRecord,
    TaskPlacementRecord,
)
from shosai.features.tasks.infrastructure.task_records import TASK_RESOURCE, TaskRecord
from shosai.features.tasks.module import TASKS
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import (
    ACCESS_POLICY,
    MEMBERSHIP_READER,
    WORKSPACE_READER,
)
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.infrastructure.membership_reader import (
    MembershipDirectory,
    WorkspaceDirectory,
)
from shosai.features.workspaces.module import WORKSPACES
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest
from tests.features.files.upload_bench import UploadBench
from tests.features.notes.no_archive import NO_ARCHIVE
from tests.features.tasks.holding_bench import Holding, holding
from tests.harness.connections import Connection
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.support.access_model import MemberRow, ResourceRow, WorkspaceRow, World
from tests.support.isolation import write_world

type Json = dict[str, Any]
HOME = Home.EU
OUTBOX = EventOutbox(EventTypes([*TASKS.events, *NOTES.events, *WORKSPACES.events]))


MEETING_COLUMNS: Final = {"title": "Созвон", "started_at": datetime.now(UTC)}
# Родитель задачи встречи для набора изоляции: сама встреча.
PARENTS: Final = {"meeting": (MEETING_RESOURCE, MEETING_COLUMNS)}


def task_columns(row: ResourceRow) -> dict[str, object]:
    """A meeting's task names its source; a task without a parent is a hand-made one."""
    return {"title": "Задача", "source": "meeting" if row.parent else "manual"}


@dataclass
class Profiles:
    """Identity's profile reader of the test: names and zones the test sets."""

    names_by_person: dict[uuid.UUID, str] = field(default_factory=dict)
    zones: dict[uuid.UUID, str] = field(default_factory=dict)

    async def profile(self, session: AsyncSession, user_id: uuid.UUID) -> AccountProfile | None:
        """The person's name and zone."""
        del session
        name = self.names_by_person.get(user_id, "Человек")
        return AccountProfile(name, "ru", self.zones.get(user_id))

    async def names(
        self, session: AsyncSession, user_ids: Collection[uuid.UUID]
    ) -> Mapping[uuid.UUID, str]:
        """The names the test set, of these people."""
        del session
        return {
            user: self.names_by_person[user] for user in user_ids if user in self.names_by_person
        }


def bearer(who: uuid.UUID, home: Home = HOME) -> dict[str, str]:
    """The person's Authorization header."""
    return {"Authorization": f"Bearer person:{who}:{home.value}"}


@dataclass
class TaskBench:
    """The task routes, the slot's homes and the test's profiles."""

    http: httpx.AsyncClient
    homes: DatabaseAccess
    profiles: Profiles
    # Соединение слота в доме EU: миры пространств пишет набор изоляции.
    connection: Connection
    files: Holding
    ports: PortDirectory

    async def call(
        self, who: uuid.UUID, method: str, path: str, body: object = None, **headers: str
    ) -> httpx.Response:
        """A request as the person."""
        return await self.http.request(method, path, json=body, headers={**bearer(who), **headers})

    async def task(
        self, owner: uuid.UUID, org: uuid.UUID | None = None, **fields: object
    ) -> uuid.UUID:
        """A task written straight to the home, as other steps leave one."""
        task_id = uuid.uuid4()
        now = datetime.now(UTC)
        values = {"title": "Позвонить", "created_at": now, "updated_at": now, **fields}
        if org is not None:
            values.setdefault("access", "organization")
        scope = TenancyScope(HOME, owner, org)
        async with self.homes.transactions.begin(scope) as session:
            session.add(TaskRecord(id=task_id, user_id=owner, org_id=org, **values))
        return task_id

    async def workspace(self, org: uuid.UUID, owner: uuid.UUID, *members: uuid.UUID) -> None:
        """An active workspace with its owner and members."""
        world = World(
            workspaces=[WorkspaceRow(org, "active")],
            members=[
                MemberRow(uuid.uuid4(), org, owner, "owner", "active"),
                *(MemberRow(uuid.uuid4(), org, member, "member", "active") for member in members),
            ],
        )
        await write_world(self.connection, TASK_RESOURCE, world)

    async def board(
        self, owner: uuid.UUID, kinds: tuple[str, ...] = ("todo", "done")
    ) -> list[uuid.UUID]:
        """A board of the person with a column of each kind given: its id, then the columns'."""
        board_id = uuid.uuid4()
        columns = [uuid.uuid4() for _ in kinds]
        async with self.homes.transactions.begin(TenancyScope(HOME, owner)) as session:
            session.add(BoardRecord(id=board_id, user_id=owner, name="Работа", icon="briefcase"))
            await session.flush()
            for position, (column_id, kind) in enumerate(zip(columns, kinds, strict=True)):
                session.add(
                    BoardColumnRecord(
                        id=column_id, board_id=board_id, user_id=owner, title=kind, kind=kind,
                        position=position,
                    )
                )  # fmt: skip
        return [board_id, *columns]

    async def place(self, owner: uuid.UUID, task_id: uuid.UUID, board: list[uuid.UUID]) -> None:
        """Put the task in the board's first column."""
        async with self.homes.transactions.begin(TenancyScope(HOME, owner)) as session:
            session.add(
                TaskPlacementRecord(
                    user_id=owner, task_id=task_id, board_id=board[0], column_id=board[1], rank="V"
                )
            )

    async def place_in(
        self, owner: uuid.UUID, task_id: uuid.UUID, at: tuple[uuid.UUID, uuid.UUID]
    ) -> None:
        """Put the task at the end of the board's column, as a card move would."""
        board_id, column_id = at
        async with self.homes.transactions.begin(TenancyScope(HOME, owner)) as session:
            spot = CardSpot(board_id, column_id, 10_000)
            await place(session, owner, task_id, spot, datetime.now(UTC))

    async def revision(self, owner: uuid.UUID, board_id: uuid.UUID) -> int:
        """The board's revision, read as its owner."""
        scope = TenancyScope(HOME, owner)
        async with self.homes.transactions.begin(scope, read_only=True) as session:
            found = await session.scalar(
                select(BoardRecord.revision).where(BoardRecord.id == board_id)
            )
        assert found is not None
        return found

    async def events(self, task_id: uuid.UUID) -> list[str]:
        """The events published about the task, oldest first."""
        async with self.homes.transactions.begin(TenancyScope(HOME), read_only=True) as session:
            rows = await session.execute(
                select(OutboxMessage.event_type, OutboxMessage.payload).order_by(
                    OutboxMessage.occurred_at, OutboxMessage.id
                )
            )
            return [kind for kind, payload in rows if payload.get("task_id") == str(task_id)]


def install_ports(
    ports: PortDirectory, profiles: Profiles, transactions: HomeTransactions, files: Holding
) -> None:
    """The test's bearer, workspaces' policy and readers, notes' readers, the test's profiles
    and plan, files' held objects."""
    ports.install(
        [
            AUTHENTICATOR.bind(BearerOfTheTest()),
            ENTITLEMENTS.bind(files.uploads.plan),
            HELD_OBJECTS.bind(files.held),
            ACCESS_POLICY.bind(
                WorkspaceAccessPolicy(
                    OUTBOX, WorkspaceAuditLog(), (MEETING_RESOURCE, TASK_RESOURCE)
                )
            ),
            MEMBERSHIP_READER.bind(MembershipDirectory()),
            WORKSPACE_READER.bind(WorkspaceDirectory()),
            ACCOUNT_PROFILE_READER.bind(profiles),
            MEETING_READER.bind(MeetingsReader(transactions, ports, NO_ARCHIVE)),
            MEETING_FINDINGS.bind(MeetingsFindings(ports)),
        ]
    )


@pytest_asyncio.fixture
async def task_bench(
    homes: DatabaseAccess, run_slot: RunSlot, upload_bench: UploadBench
) -> AsyncIterator[TaskBench]:
    """The task routes over the slot's homes, with files' held objects over its buckets."""
    profiles = Profiles()
    transactions = homes.transactions
    ports = PortDirectory()
    effects = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    async with holding(upload_bench, ports, run_slot) as files:
        install_ports(ports, profiles, transactions, files)
        services = (
            TaskReads(transactions, ports),
            TaskWrites(transactions, ports, (OUTBOX, effects)),
            TaskEdits(transactions, ports, OUTBOX),
        )
        threads = (Subtasks(transactions, ports), Comments(transactions, ports, effects))
        routers = (
            build_tasks_router(services, ports),
            build_threads_router(threads, ports),
            build_attachments_router(Attachments(transactions, ports), ports),
            build_boards_router(
                (BoardReads(transactions, ports), BoardWrites(transactions, ports, OUTBOX)), ports
            ),
            build_board_parts_router(
                (Columns(transactions), Cards(transactions, ports, (services[1], services[2]))),
                ports,
            ),
            build_stickers_router((Stickers(transactions), BoardStickers(transactions)), ports),
            build_values_router(Values(transactions, ports), ports),
        )
        async with client_of(build_probe_app(extra=routers).app) as http:
            connection = run_slot.claimed.connections[HOME]
            yield TaskBench(http, homes, profiles, connection, files, ports)
