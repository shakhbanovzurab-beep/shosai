"""The inv-14 self-test and the inv-16 seat check set their gauges (§16.4)."""

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
import sqlalchemy as sa
from prometheus_client import CollectorRegistry

from shosai.core.access.shareable import ShareableResource
from shosai.core.config.roles import ProcessRole
from shosai.core.kernel.homes import Home
from shosai.features.workspaces.application.admission import Joining
from shosai.features.workspaces.application.invariant_checks import PolicySelfTest, SeatCheck
from shosai.features.workspaces.contracts import Viewer
from shosai.features.workspaces.contracts.events import JoinChannel
from shosai.features.workspaces.domain.roles import WorkspaceRole
from tests.features.workspaces.probe_resources import FILES, NOTES
from tests.features.workspaces.services import FixedSeats, created, ports_with, services
from tests.features.workspaces.test_access_policy import policy
from tests.harness.database_access import (
    DatabaseAccess,
    ProcessShape,
    open_database_access,
    slot_urls,
)
from tests.harness.run_slot import RunSlot
from tests.support.isolation import canonical_world, write_world


@pytest_asyncio.fixture
async def workers(run_slot: RunSlot) -> AsyncIterator[DatabaseAccess]:
    """The database access of a workers process: it may open sweeps."""
    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as access:
        await access.gate.verify_at_start()
        yield access


class OpenToAll:
    """A broken policy that admits every row: the self-test must notice it."""

    def readable(self, _resource: ShareableResource, _viewer: Viewer) -> sa.ColumnElement[bool]:
        return sa.true()


def gauge(registry: CollectorRegistry, name: str, home: Home) -> float | None:
    return registry.get_sample_value(name, {"home": home.value})


async def test_the_self_test_is_quiet_on_the_policy_and_fires_on_a_broken_one(
    homes: DatabaseAccess, workers: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[Home.RU]
    await write_world(connection, NOTES, canonical_world("meeting").world)
    await write_world(connection, FILES, canonical_world("file").world)
    quiet, loud = CollectorRegistry(), CollectorRegistry()
    resources = (NOTES, FILES)

    clean = await PolicySelfTest(workers.transactions, policy(), resources, quiet).run(Home.RU)
    found = await PolicySelfTest(workers.transactions, OpenToAll(), resources, loud).run(Home.RU)

    assert clean == 0
    assert gauge(quiet, "shosai_workspaces_policy_rls_disagreements", Home.RU) == 0
    assert found is not None
    assert found > 0
    assert gauge(loud, "shosai_workspaces_policy_rls_disagreements", Home.RU) == found


async def test_the_seat_check_counts_overfull_workspaces_and_waits_for_billing(
    homes: DatabaseAccess, workers: DatabaseAccess
) -> None:
    seats = FixedSeats(paid=0)
    found = services(homes, seats)
    workspace = await created(found, Home.EU, uuid.uuid4())
    for _ in range(2):
        joining = Joining(
            workspace.org_id, uuid.uuid4(), Home.EU, WorkspaceRole.MEMBER, JoinChannel.DOMAIN
        )
        await found.admission.admit(Home.EU, joining)
    registry = CollectorRegistry()

    def check(paid: int | None, into: CollectorRegistry) -> SeatCheck:
        bound = ports_with(None if paid is None else FixedSeats(paid=paid))
        return SeatCheck(workers.transactions, bound, into)

    unbound = await check(None, CollectorRegistry()).run(Home.EU)
    within = await check(3, CollectorRegistry()).run(Home.EU)
    over = await check(2, registry).run(Home.EU)

    assert unbound is None
    assert within == 0
    assert over == 1
    assert gauge(registry, "shosai_workspaces_over_seats", Home.EU) == 1
