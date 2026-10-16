"""Two fixture slices that use every part a `FeatureModule` offers (draft lesson: feature
start hooks nothing called).

`notes` declares an event, an HTTP route, a task, a scheduler loop and a readiness probe;
`digest` subscribes to the event of `notes` and serves a WebSocket-gateway route. Both
record when their build is entered and left, so a test sees the lifecycle in order.
`native_breaking_feature` serves a route of the shipped native clients in a shape they
cannot decode, for the native-contract gate.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import ClassVar
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.events.domain_event import DomainEvent
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.core.health.probes import DependencyProbe
from shosai.core.ports.keys import PortKey
from shosai.core.runtime.loops import ScheduledLoop
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler
from shosai.core.tasks.payloads import TaskPayload
from shosai.core.tasks.queues import TaskQueue

NOTES_ROUTE = "/v1/fixture-notes"
# Нативный маршрут macOS и Windows 1.4.5 (contracts/draft/consumers.json).
NATIVE_ROUTE = "/v1/auth/me"
DIGEST_ROUTE = "/v1/ws/fixture-digest/status"


class NoteWritten(DomainEvent):
    """A fixture note was written."""

    event_type: ClassVar[str] = "notes.note.written"
    version: ClassVar[int] = 1

    note_id: UUID


class TidyNotes(TaskPayload):
    """The payload of the fixture task."""


TIDY_NOTES = TaskDeclaration(
    name="notes.tidy",
    queue=TaskQueue.DEFAULT,
    payload=TidyNotes,
    deadline=timedelta(seconds=5),
    retry=NO_RETRY,
)


@dataclass
class Lifecycle:
    """What the fixture slices did, in order."""

    events: list[str] = field(default_factory=list)


def notes_feature(lifecycle: Lifecycle, *, probe_name: str = "notes.index") -> FeatureModule:
    """A slice with an event, a route, a task, a loop and a probe."""

    @asynccontextmanager
    async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
        lifecycle.events.append(f"notes:open:{services.role.value}")
        router = APIRouter(prefix=NOTES_ROUTE)

        @router.get("")
        async def read_notes() -> dict[str, str]:
            """The role that serves the fixture route."""
            return {"role": services.role.value}

        async def tidy(_payload: TidyNotes) -> None:
            lifecycle.events.append("notes:tidy")

        async def sweep() -> None:
            lifecycle.events.append("notes:sweep")

        async def index_answers() -> None:
            lifecycle.events.append("notes:probe")

        try:
            yield FeatureParts(
                http_routers=(router,),
                task_handlers=(TaskHandler(TIDY_NOTES, tidy),),
                loops=(ScheduledLoop("notes.sweep", timedelta(seconds=60), sweep),),
                probes=(DependencyProbe(probe_name, index_answers, ()),),
            )
        finally:
            lifecycle.events.append("notes:close")

    return FeatureModule(name="notes", build=build, events=(NoteWritten,))


def digest_feature(lifecycle: Lifecycle) -> FeatureModule:
    """A slice consuming the event of `notes` and serving a route of the WS gateway."""

    async def collect(_session: AsyncSession, received: ReceivedEvent[NoteWritten]) -> None:
        lifecycle.events.append(f"digest:collect:{received.event.note_id}")

    @asynccontextmanager
    async def build(_services: CoreServices) -> AsyncIterator[FeatureParts]:
        lifecycle.events.append("digest:open")
        router = APIRouter(prefix=DIGEST_ROUTE)

        @router.get("")
        async def digest_status() -> dict[str, str]:
            """The fixture gateway route."""
            return {"status": "ok"}

        subscription = EventSubscription(
            consumer="digest.collect",
            event=NoteWritten,
            queue=TaskQueue.DEFAULT,
            deadline=timedelta(seconds=5),
            handle=collect,
        )
        try:
            yield FeatureParts(ws_routers=(router,), subscriptions=(subscription,))
        finally:
            lifecycle.events.append("digest:close")

    return FeatureModule(name="digest", build=build)


def broken_feature(lifecycle: Lifecycle) -> FeatureModule:
    """A slice whose build fails, after the slices listed before it were built."""

    @asynccontextmanager
    async def build(_services: CoreServices) -> AsyncIterator[FeatureParts]:
        lifecycle.events.append("broken:open")
        await open_client()
        yield FeatureParts()

    return FeatureModule(name="broken", build=build)


def native_breaking_feature(name: str, events: tuple[type[DomainEvent], ...] = ()) -> FeatureModule:
    """A slice serving a native route with a response the shipped clients cannot decode.

    It declares the `events` of the slice it replaces: other slices subscribe to them.
    """

    @asynccontextmanager
    async def build(_services: CoreServices) -> AsyncIterator[FeatureParts]:
        router = APIRouter(prefix=NATIVE_ROUTE)

        @router.get("")
        async def read_account() -> dict[str, str]:
            """A response without the fields the native clients read."""
            return {"nickname": "fixture"}

        yield FeatureParts(http_routers=(router,))

    return FeatureModule(name=name, build=build, events=events)


class Clock:
    """The service the fixture port offers."""

    def now(self) -> str:
        """A fixed answer."""
        return "fixture-now"


CLOCK = PortKey[Clock]("clocks.clock")


def clock_feature() -> FeatureModule:
    """A slice that binds the fixture port."""

    @asynccontextmanager
    async def build(_services: CoreServices) -> AsyncIterator[FeatureParts]:
        yield FeatureParts(provides=(CLOCK.bind(Clock()),))

    return FeatureModule(name="clocks", build=build)


def clock_reader_feature() -> FeatureModule:
    """A slice that requires the fixture port, listed before the slice that binds it."""
    return FeatureModule(name="reader", requires=(CLOCK,))


async def open_client() -> None:
    """A client of the broken slice that never opens."""
    message = "клиент среза не открылся"
    raise RuntimeError(message)
