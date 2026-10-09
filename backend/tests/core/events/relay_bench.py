"""A sender the relay tests put in place of the task sender, and an outbox filler."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy.pool import QueuePool

from shosai.core.db.engines import HomeDatabases
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.delivery import EventDeliveryPayload
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.tasks.declaration import TaskDeclaration
from shosai.core.tasks.payloads import TaskPayload
from tests.core.events.bench import NoteState, NoteWritten


def connections_in_use(databases: HomeDatabases) -> int:
    """Connections the process holds in every home's pool right now."""
    pools = [databases.engine(home).pool for home in Home]
    return sum(pool.checkedout() for pool in pools if isinstance(pool, QueuePool))


@dataclass
class RecordingSender:
    """Records each send and the connections held at that moment; raises planned failures."""

    databases: HomeDatabases
    # Сбой по номеру попытки отправки, с единицы.
    failures: dict[int, Exception] = field(default_factory=dict)
    before_first_send: Callable[[], Awaitable[None]] | None = None
    attempts: int = 0
    sent: list[tuple[str, EventDeliveryPayload]] = field(default_factory=list)
    held_connections: list[int] = field(default_factory=list)

    async def send[P: TaskPayload](self, task: TaskDeclaration[P], payload: P) -> str:
        """Record the send, or raise the failure planned for this attempt."""
        self.attempts += 1
        self.held_connections.append(connections_in_use(self.databases))
        if self.before_first_send is not None:
            hook, self.before_first_send = self.before_first_send, None
            await hook()
        failure = self.failures.get(self.attempts)
        if failure is not None:
            raise failure
        if not isinstance(payload, EventDeliveryPayload):
            message = "relay отправляет только доставки событий"
            raise TypeError(message)
        self.sent.append((task.name, payload))
        return uuid.uuid4().hex

    def event_ids(self) -> list[uuid.UUID]:
        """The event of each successful send, in order."""
        return [payload.event_id for _, payload in self.sent]


async def write_notes(
    transactions: HomeTransactions, outbox: EventOutbox, home: Home, count: int
) -> list[uuid.UUID]:
    """Write `count` probe events in one transaction of the home; return their ids."""
    async with transactions.begin(TenancyScope(home)) as session:
        return [
            await outbox.add(session, NoteWritten(record_id=uuid.uuid4(), state=NoteState.DRAFT))
            for _ in range(count)
        ]
