"""The policy's `= ANY(...)` pre-filters admit exactly what its `IN (subquery)` ones did.

On random worlds of both share kinds, every person reads and manages the same rows through
the current predicates as through the frozen former ones (`legacy_predicates`), across
every space and narrowed to each workspace, under the application role and row-level
security, as a slice's query runs them.
"""

import uuid

import sqlalchemy as sa
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.contracts import Viewer
from tests.features.workspaces.legacy_predicates import legacy_manageable, legacy_readable
from tests.features.workspaces.random_worlds import worlds
from tests.features.workspaces.test_access_policy import POLICY_PROPERTY, RESOURCES, policy
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.support.isolation import write_world


async def admitted(
    homes: DatabaseAccess, table: sa.Table, viewer: uuid.UUID, predicate: sa.ColumnElement[bool]
) -> set[uuid.UUID]:
    """The rows a predicate admits for the viewer, in their scope."""
    async with homes.transactions.begin(TenancyScope(Home.EU, viewer), read_only=True) as session:
        return set(await session.scalars(sa.select(table.c.id).where(predicate)))


@POLICY_PROPERTY
@given(data=st.data(), kind=st.sampled_from(["meeting", "file"]))
async def test_the_any_form_admits_exactly_what_the_in_form_admitted(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot, data: st.DataObject, kind: str
) -> None:
    world, people = data.draw(worlds(kind))
    resource = RESOURCES[kind]
    await write_world(run_slot.claimed.connections[Home.EU], resource, world)
    spaces = [None, *(workspace.id for workspace in world.workspaces)]

    for person in people:
        for within in spaces:
            viewer = Viewer(person, within)
            pairs = (
                (policy().readable(resource, viewer), legacy_readable(resource, person, within)),
                (
                    policy().manageable(resource, viewer),
                    legacy_manageable(resource, person, within),
                ),
            )
            for current, former in pairs:
                table = resource.table
                now = await admitted(homes, table, person, current)
                assert now == await admitted(homes, table, person, former), (kind, within)
