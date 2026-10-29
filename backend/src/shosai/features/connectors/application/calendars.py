"""The `CALENDARS` binding: each call through the connection's provider session, to the
calendar adapter of the connection's app (plan §3.3). Providers bring their adapters with
their steps — Google Calendar (step 10), Outlook (13), CalDAV and Yandex (16)."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol
from uuid import UUID

from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.provider_access import ConnectorProviderAccess
from shosai.features.connectors.contracts.calendars import (
    CalendarNotification,
    CalendarUnsupportedError,
    ChangesQuery,
    EventChanges,
    EventPage,
    EventTarget,
    EventWrite,
    RemoteCalendar,
    RemoteEvent,
    WatchChannel,
    WatchRequest,
    WindowQuery,
)
from shosai.features.connectors.contracts.provider import ProviderSession
from shosai.features.connectors.domain.catalogue import App


class CalendarAdapter(Protocol):
    """One provider's calendar API over an authorized session."""

    async def calendars(self, session: ProviderSession) -> tuple[RemoteCalendar, ...]:
        """The account's calendars."""
        ...

    async def window(self, session: ProviderSession, query: WindowQuery) -> EventPage:
        """Occurrences in a window."""
        ...

    async def changes(self, session: ProviderSession, query: ChangesQuery) -> EventChanges:
        """One page of a sync pass."""
        ...

    async def write(self, session: ProviderSession, write: EventWrite) -> RemoteEvent:
        """Create or change an event."""
        ...

    async def delete(self, session: ProviderSession, target: EventTarget) -> None:
        """Delete an event."""
        ...

    async def watch(self, session: ProviderSession, request: WatchRequest) -> WatchChannel:
        """Open a push channel."""
        ...

    async def stop(self, session: ProviderSession, channel: WatchChannel) -> None:
        """Close a push channel."""
        ...

    def notification(self, headers: Mapping[str, str]) -> CalendarNotification | None:
        """A push notification from its headers."""
        ...


class ConnectorCalendars:
    """Calendars of every provider behind one port."""

    def __init__(
        self, access: ConnectorProviderAccess, adapters: Mapping[App, CalendarAdapter]
    ) -> None:
        self._access = access
        self._adapters = adapters

    async def _run[T](
        self,
        scope: TenancyScope,
        connection_id: UUID,
        call: Callable[[CalendarAdapter, ProviderSession], Awaitable[T]],
    ) -> T:
        async with self._access.open(scope, connection_id) as session:
            adapter = self._adapters.get(session.connection.app)
            if adapter is None:
                raise CalendarUnsupportedError
            return await call(adapter, session)

    async def calendars(
        self, scope: TenancyScope, connection_id: UUID
    ) -> tuple[RemoteCalendar, ...]:
        """The account's calendars."""
        return await self._run(scope, connection_id, lambda a, s: a.calendars(s))

    async def window(
        self, scope: TenancyScope, connection_id: UUID, query: WindowQuery
    ) -> EventPage:
        """Occurrences of one calendar in a window."""
        return await self._run(scope, connection_id, lambda a, s: a.window(s, query))

    async def changes(
        self, scope: TenancyScope, connection_id: UUID, query: ChangesQuery
    ) -> EventChanges:
        """One page of a sync pass."""
        return await self._run(scope, connection_id, lambda a, s: a.changes(s, query))

    async def write(
        self, scope: TenancyScope, connection_id: UUID, write: EventWrite
    ) -> RemoteEvent:
        """Create an event, or change one whose etag is current."""
        return await self._run(scope, connection_id, lambda a, s: a.write(s, write))

    async def delete(self, scope: TenancyScope, connection_id: UUID, target: EventTarget) -> None:
        """Delete an event."""
        await self._run(scope, connection_id, lambda a, s: a.delete(s, target))

    async def watch(
        self, scope: TenancyScope, connection_id: UUID, request: WatchRequest
    ) -> WatchChannel:
        """Open a push channel on one calendar."""
        return await self._run(scope, connection_id, lambda a, s: a.watch(s, request))

    async def stop(self, scope: TenancyScope, connection_id: UUID, channel: WatchChannel) -> None:
        """Close a push channel."""
        await self._run(scope, connection_id, lambda a, s: a.stop(s, channel))

    def notification(self, app: str, headers: Mapping[str, str]) -> CalendarNotification | None:
        """A push notification's meaning; None for an app without calendars or a stray call."""
        try:
            adapter = self._adapters.get(App(app))
        except ValueError:
            return None
        return None if adapter is None else adapter.notification(headers)
