"""Joining, roles, teams, removal and leaving (§7, §3.6 flow 3; inv-15, inv-16, inv-17)."""

import uuid

import pytest
import sqlalchemy as sa

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.application.admission import Joining
from shosai.features.workspaces.application.teams import TeamDraft
from shosai.features.workspaces.contracts.events import JoinChannel
from shosai.features.workspaces.domain.roles import WorkspaceRole
from tests.features.workspaces.services import (
    FixedSeats,
    Services,
    audit_actions,
    created,
    services,
)
from tests.harness.connections import fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

HOME = Home.RU


async def join(
    found: Services, org_id: uuid.UUID, user: uuid.UUID, role: WorkspaceRole = WorkspaceRole.MEMBER
) -> uuid.UUID:
    return await found.admission.admit(HOME, Joining(org_id, user, HOME, role, JoinChannel.DOMAIN))


async def test_joins_fill_the_paid_seats_and_stop_there(homes: DatabaseAccess) -> None:
    seats = FixedSeats(paid=0)
    found = services(homes, seats)
    workspace = await created(found, HOME, uuid.uuid4())
    seats.paid = 3

    await join(found, workspace.org_id, uuid.uuid4())
    await join(found, workspace.org_id, uuid.uuid4())

    with pytest.raises(AppError, match="seats_exhausted"):
        await join(found, workspace.org_id, uuid.uuid4())


async def test_nobody_joins_before_billing_binds_its_seats(homes: DatabaseAccess) -> None:
    workspace = await created(services(homes, FixedSeats(paid=0)), HOME, uuid.uuid4())

    with pytest.raises(AppError, match="seats_unavailable"):
        await join(services(homes, None), workspace.org_id, uuid.uuid4())


async def test_a_person_of_another_home_does_not_join(homes: DatabaseAccess) -> None:
    found = services(homes, FixedSeats(paid=0))
    workspace = await created(found, HOME, uuid.uuid4())
    joining = Joining(
        workspace.org_id, uuid.uuid4(), Home.EU, WorkspaceRole.MEMBER, JoinChannel.DOMAIN
    )

    with pytest.raises(AppError, match="workspace_home_mismatch"):
        await found.admission.admit(HOME, joining)


async def test_a_repeated_join_returns_the_same_membership_and_a_removed_member_comes_back(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    found, owner, person = services(homes, FixedSeats(paid=0)), uuid.uuid4(), uuid.uuid4()
    workspace = await created(found, HOME, owner)

    first = await join(found, workspace.org_id, person)
    again = await join(found, workspace.org_id, person)
    await found.members.remove(TenancyScope(HOME, owner, workspace.org_id), first)
    back = await join(found, workspace.org_id, person)

    state = await fetch_value(
        run_slot.claimed.connections[HOME], "SELECT state FROM memberships WHERE id = %s", (first,)
    )
    assert first == again == back
    assert state == "active"


async def test_roles_change_by_the_domains_rules_with_one_audit_row_each(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    found, owner, admin, member = (
        services(homes, FixedSeats(paid=0)),
        *(uuid.uuid4() for _ in range(3)),
    )
    workspace = await created(found, HOME, owner)
    admin_seat = await join(found, workspace.org_id, admin)
    member_seat = await join(found, workspace.org_id, member)
    as_owner = TenancyScope(HOME, owner, workspace.org_id)
    as_member = TenancyScope(HOME, member, workspace.org_id)

    await found.members.change_role(as_owner, admin_seat, WorkspaceRole.ADMIN)
    for scope, target, role in (
        (as_member, admin_seat, WorkspaceRole.MEMBER),
        (as_owner, workspace.membership_id, WorkspaceRole.ADMIN),
        (as_owner, member_seat, WorkspaceRole.OWNER),
    ):
        with pytest.raises(AppError, match="not_allowed"):
            await found.members.change_role(scope, target, role)

    actions = await audit_actions(run_slot.claimed.connections[HOME])
    assert actions.count("role_changed") == 1


async def test_a_member_joins_only_open_teams_and_an_admin_places_anyone(
    homes: DatabaseAccess,
) -> None:
    found, owner, member = services(homes, FixedSeats(paid=0)), uuid.uuid4(), uuid.uuid4()
    workspace = await created(found, HOME, owner)
    seat = await join(found, workspace.org_id, member)
    as_owner = TenancyScope(HOME, owner, workspace.org_id)
    as_member = TenancyScope(HOME, member, workspace.org_id)
    open_team = await found.teams.create_team(
        as_owner, TeamDraft("Open", "", "sky", private=False, member_ids=frozenset())
    )
    closed = await found.teams.create_team(
        as_owner, TeamDraft("Closed", "", "rose", private=True, member_ids=frozenset())
    )

    await found.members.set_teams(as_member, seat, {open_team})
    with pytest.raises(AppError, match="not_allowed"):
        await found.members.set_teams(as_member, seat, {open_team, closed})
    await found.members.set_teams(as_owner, seat, {closed})
    with pytest.raises(AppError, match="teams_invalid"):
        await found.members.set_teams(as_owner, seat, {uuid.uuid4()})


async def test_a_removed_member_loses_the_workspace_at_once_and_keeps_personal(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    found, owner, member = services(homes, FixedSeats(paid=0)), uuid.uuid4(), uuid.uuid4()
    workspace = await created(found, HOME, owner)
    seat = await join(found, workspace.org_id, member)
    connection = run_slot.claimed.connections[HOME]
    teams = sa.text("SELECT count(*) FROM teams")
    await found.teams.create_team(
        TenancyScope(HOME, owner, workspace.org_id),
        TeamDraft("Core", "", "blue", private=False, member_ids=frozenset({seat})),
    )

    async with homes.transactions.begin(TenancyScope(HOME, member)) as session:
        before = await session.scalar(teams)
        await found.members.remove(TenancyScope(HOME, owner, workspace.org_id), seat)
        after = await session.scalar(teams)
        own = await session.scalar(sa.text("SELECT count(*) FROM memberships"))

    assert (before, after) == (1, 0)
    # Свои членства человек видит и после удаления: экспорт, перенос, Personal.
    assert own == 1
    assert await fetch_value(connection, "SELECT count(*) FROM team_members") == 0
    events = await fetch_rows(
        connection,
        "SELECT payload FROM outbox_messages WHERE event_type = 'workspaces.member.removed'",
    )
    assert events[0]["payload"]["successor_user_id"] == str(owner)


async def test_the_owner_hands_over_before_leaving_and_a_member_just_leaves(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    found, owner, member = services(homes, FixedSeats(paid=0)), uuid.uuid4(), uuid.uuid4()
    workspace = await created(found, HOME, owner)
    await join(found, workspace.org_id, member)

    with pytest.raises(AppError, match="owner_cannot_leave"):
        await found.members.leave(TenancyScope(HOME, owner, workspace.org_id))
    await found.members.leave(TenancyScope(HOME, member, workspace.org_id))
    with pytest.raises(AppError, match="workspace_not_found"):
        await found.members.leave(TenancyScope(HOME, member, workspace.org_id))

    actions = await audit_actions(run_slot.claimed.connections[HOME])
    assert actions == ["workspace_created", "member_joined", "member_left"]
