"""`CONNECTIONS` for consumers: the person's own views, never a stranger's, and a personal
connection serving a workspace only while its person is an active member there (CN-D3)."""

import uuid

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.connectors.application.registry import ConnectorRegistry
from shosai.features.connectors.domain.catalogue import App, Capability
from tests.features.connectors.connect_bench import connect_bench
from tests.features.connectors.lifecycle_bench import LifecycleBench, lifecycle

__all__ = ["connect_bench", "lifecycle"]


async def test_a_consumer_reads_the_person_s_connections_by_capability(
    lifecycle: LifecycleBench,
) -> None:
    person, stranger = (Home.RU, uuid.uuid4()), (Home.RU, uuid.uuid4())
    await lifecycle.connected(person, App.GOOGLE_CALENDAR)
    await lifecycle.connected(person, App.GOOGLE_DRIVE)
    registry = ConnectorRegistry(lifecycle.connect.ports)
    transactions = lifecycle.connect.homes.transactions

    async with transactions.begin(TenancyScope(*person), read_only=True) as session:
        every = await registry.of_person(session, person[1])
        calendars = await registry.of_person(session, person[1], Capability.CALENDAR)
        one = await registry.get(session, calendars[0].id)
    async with transactions.begin(TenancyScope(*stranger), read_only=True) as session:
        hidden = await registry.get(session, calendars[0].id)
        theirs = await registry.of_person(session, person[1])

    assert sorted(view.app for view in every) == [App.GOOGLE_CALENDAR, App.GOOGLE_DRIVE]
    assert [view.app for view in calendars] == [App.GOOGLE_CALENDAR]
    assert one == calendars[0]
    assert "token" not in repr(one)
    assert (hidden, theirs) == (None, ())


async def test_a_personal_connection_serves_a_workspace_only_through_membership(
    lifecycle: LifecycleBench,
) -> None:
    person = (Home.RU, uuid.uuid4())
    member_of, other = uuid.uuid4(), uuid.uuid4()
    lifecycle.connect.workspaces.admins[member_of] = {person[1]}
    await lifecycle.connected(person, App.GOOGLE_CALENDAR)
    registry = ConnectorRegistry(lifecycle.connect.ports)

    async with lifecycle.connect.homes.transactions.begin(TenancyScope(*person)) as session:
        (view,) = await registry.of_person(session, person[1])
        served = await registry.usable_for(session, view.id, member_of)
        refused = await registry.usable_for(session, view.id, other)
        missing = await registry.usable_for(session, uuid.uuid4(), member_of)

    assert (served, refused, missing) == (True, False, False)
