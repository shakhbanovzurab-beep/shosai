"""Leo's write tools of `notes` over the slot's homes: the steps, the services, the audit."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from prometheus_client import CollectorRegistry
from sqlalchemy import func, select

from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.records import OutboxMessage
from shosai.core.idempotency.action_items import ActionItems
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.notes.application.library import MeetingLibrary
from shosai.features.notes.application.share_links import ShareLinks
from shosai.features.notes.application.write_up_rewrites import WriteUpRewrites
from shosai.features.notes.channels.agent_link_writes import LinkWrites
from shosai.features.notes.channels.agent_tool_writes import NoteWrites, WriteSteps
from shosai.features.notes.domain.runs import Stage
from shosai.features.notes.infrastructure.notes_records import FolderRecord
from shosai.features.notes.module import NOTES
from shosai.features.workspaces.module import WORKSPACES
from tests.features.notes.library_bench import library_ports
from tests.harness.database_access import DatabaseAccess

HOME = Home.EU
AUDIT = ActionItemExecuted.event_type


@dataclass
class StartedRuns:
    """The run starter of the test: it records each stage it was asked to send."""

    kicked: list[tuple[uuid.UUID, Stage]] = field(default_factory=list)

    async def kick(self, scope: TenancyScope, run_id: uuid.UUID, stage: Stage) -> None:
        """Record the stage instead of sending it."""
        del scope
        self.kicked.append((run_id, stage))


@dataclass(frozen=True, slots=True)
class WriteBench:
    """The two groups of write tools and what the tests read back."""

    homes: DatabaseAccess
    notes: NoteWrites
    links: LinkWrites
    started: StartedRuns

    def context(self, person: uuid.UUID) -> ToolContext:
        """A call acting for the person, in the EU home."""
        return ToolContext(
            TenancyScope(HOME, person), uuid.uuid4(), datetime.now(UTC) + timedelta(minutes=1)
        )

    async def folder(self, owner: uuid.UUID, name: str) -> uuid.UUID:
        """A folder of the person's."""
        folder_id = uuid.uuid4()
        async with self.homes.transactions.begin(TenancyScope(HOME, owner)) as session:
            session.add(FolderRecord(id=folder_id, user_id=owner, name=name, color="green"))
        return folder_id

    async def audited(self, person: uuid.UUID) -> int:
        """How many action items took effect, as their audit events say."""
        async with self.homes.transactions.begin(
            TenancyScope(HOME, person), read_only=True
        ) as session:
            count = await session.scalar(
                select(func.count())
                .select_from(OutboxMessage)
                .where(OutboxMessage.event_type == AUDIT)
            )
        return int(count or 0)


@pytest.fixture
def write_bench(homes: DatabaseAccess) -> WriteBench:
    """The write tools as the module binds them, with a starter that sends nothing."""
    transactions, ports = homes.transactions, library_ports()
    effects = EffectLedger(EffectKeyMetrics(CollectorRegistry()))
    outbox = EventOutbox(EventTypes([*NOTES.events, *WORKSPACES.events, ActionItemExecuted]))
    steps = WriteSteps(transactions, (ports, ActionItems(effects, outbox)))
    started = StartedRuns()
    rewrites = WriteUpRewrites(transactions, (ports, effects, started))
    return WriteBench(
        homes,
        NoteWrites(steps, (MeetingLibrary(transactions, ports), rewrites)),
        LinkWrites(steps, ShareLinks(transactions, ports)),
        started,
    )
