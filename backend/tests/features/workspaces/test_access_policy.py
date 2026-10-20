"""The access policy against §7: the kit, random worlds, narrowing, the batch re-check."""

import uuid

import pytest
import sqlalchemy as sa
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from shosai.core.access.shareable import ShareableResource
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.contracts import Viewer
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.features.workspaces.probe_resources import FILES, NOTES
from tests.features.workspaces.random_worlds import worlds
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot
from tests.support.access_model import manageable, readable
from tests.support.isolation import assert_isolated, canonical_world, write_world

RESOURCES = {"meeting": NOTES, "file": FILES}
POLICY_PROPERTY = settings(
    max_examples=60,
    deadline=None,
    # Каждый пример пишет мир с новыми id; фикстура homes очищает таблицы после теста.
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)


def policy() -> WorkspaceAccessPolicy:
    return WorkspaceAccessPolicy(
        EventOutbox(EventTypes(list(WORKSPACES.events))), WorkspaceAuditLog()
    )


async def seen(
    homes: DatabaseAccess,
    home: Home,
    resource: ShareableResource,
    viewer: Viewer,
    *,
    manage: bool = False,
) -> set[uuid.UUID]:
    """What the policy's predicate returns to the viewer, under the application role and RLS."""
    predicate = (policy().manageable if manage else policy().readable)(resource, viewer)
    async with homes.transactions.begin(
        TenancyScope(home, viewer.user_id), read_only=True
    ) as session:
        return set(await session.scalars(sa.select(resource.table.c.id).where(predicate)))


@pytest.mark.parametrize("home", list(Home))
@pytest.mark.parametrize("kind", ["meeting", "file"])
async def test_the_kit_holds_for_both_share_kinds(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot, home: Home, kind: str
) -> None:
    resource = RESOURCES[kind]

    async def path(viewer: Viewer) -> set[uuid.UUID]:
        return await seen(homes, home, resource, viewer)

    await assert_isolated(run_slot.claimed.connections[home], resource, path)


@POLICY_PROPERTY
@given(data=st.data(), kind=st.sampled_from(["meeting", "file"]))
async def test_the_policy_agrees_with_the_rules_on_random_worlds(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot, data: st.DataObject, kind: str
) -> None:
    world, people = data.draw(worlds(kind))
    resource = RESOURCES[kind]
    await write_world(run_slot.claimed.connections[Home.EU], resource, world)

    for person in people:
        assert await seen(homes, Home.EU, resource, Viewer(person)) == readable(world, kind, person)
        assert await seen(homes, Home.EU, resource, Viewer(person), manage=True) == manageable(
            world, kind, person
        )
        for org in world.workspaces:
            narrowed = await seen(homes, Home.EU, resource, Viewer(person, within=org.id))
            assert narrowed == readable(world, kind, person, within=org.id)


async def test_a_workspace_screen_narrows_to_its_workspace_and_leo_does_not(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    canon = canonical_world("meeting")
    await write_world(run_slot.claimed.connections[Home.RU], NOTES, canon.world)
    carol = canon.people["carol"]
    org_b = canon.workspaces["b"]

    everywhere = await seen(homes, Home.RU, NOTES, Viewer(carol))
    in_b = await seen(homes, Home.RU, NOTES, Viewer(carol, within=org_b))

    assert in_b == readable(canon.world, "meeting", carol, within=org_b)
    assert in_b < everywhere


async def test_revoked_hits_are_dropped_by_the_batch_check(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    canon = canonical_world("file")
    connection = run_slot.claimed.connections[Home.EU]
    await write_world(connection, FILES, canon.world)
    frank = Viewer(canon.people["frank"])
    candidates = {row.id for row in canon.world.rows}

    async with homes.transactions.begin(TenancyScope(Home.EU, frank.user_id)) as session:
        before = await policy().filter_readable(session, FILES, candidates, frank)
    await connection.execute("DELETE FROM resource_grants WHERE resource_kind = 'knowledge_item'")
    async with homes.transactions.begin(TenancyScope(Home.EU, frank.user_id)) as session:
        after = await policy().filter_readable(session, FILES, candidates, frank)
        nothing = await policy().filter_readable(session, FILES, [], frank)

    assert before == readable(canon.world, "file", frank.user_id)
    assert len(before - after) == 1
    assert nothing == frozenset()
