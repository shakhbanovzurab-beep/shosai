"""Teams and projects: who changes them, the knowledge guard, the audit and the events (§7)."""

import uuid

import pytest

from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.application.admission import Joining
from shosai.features.workspaces.application.teams import ProjectDraft, TeamDraft
from shosai.features.workspaces.contracts.events import JoinChannel
from shosai.features.workspaces.domain.roles import WorkspaceRole
from tests.features.workspaces.services import (
    FixedSeats,
    audit_actions,
    created,
    event_types,
    services,
)
from tests.harness.connections import fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

HOME = Home.EU
CORE = TeamDraft("Core", "The core team", "violet", private=False, member_ids=frozenset())


def project(lead: uuid.UUID | None = None) -> ProjectDraft:
    return ProjectDraft("Launch", "", "planned", lead, None, None)


async def test_admins_shape_teams_and_members_do_not(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    found, owner, member = services(homes, FixedSeats(paid=0)), uuid.uuid4(), uuid.uuid4()
    workspace = await created(found, HOME, owner)
    seat = await found.admission.admit(
        HOME, Joining(workspace.org_id, member, HOME, WorkspaceRole.MEMBER, JoinChannel.DOMAIN)
    )
    as_owner = TenancyScope(HOME, owner, workspace.org_id)

    team = await found.teams.create_team(as_owner, CORE)
    await found.teams.update_team(
        as_owner, team, TeamDraft("Core", "", "sky", private=True, member_ids=frozenset({seat}))
    )
    with pytest.raises(AppError, match="not_allowed"):
        await found.teams.create_team(TenancyScope(HOME, member, workspace.org_id), CORE)
    with pytest.raises(AppError, match="members_invalid"):
        await found.teams.update_team(
            as_owner,
            team,
            TeamDraft("Core", "", "sky", private=True, member_ids=frozenset({uuid.uuid4()})),
        )
    await found.teams.delete_team(as_owner, team)

    connection = run_slot.claimed.connections[HOME]
    assert await audit_actions(connection) == [
        "workspace_created", "member_joined", "team_created", "team_changed", "team_deleted",
    ]  # fmt: skip
    assert "workspaces.team.deleted" in await event_types(connection)


async def test_a_team_with_knowledge_stays_and_its_meeting_grants_go_with_it(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    found, owner = services(homes, FixedSeats(paid=0)), uuid.uuid4()
    workspace = await created(found, HOME, owner)
    as_owner = TenancyScope(HOME, owner, workspace.org_id)
    team = await found.teams.create_team(as_owner, CORE)
    connection = run_slot.claimed.connections[HOME]
    grant = (
        "INSERT INTO resource_grants (org_id, resource_kind, resource_id, grantee_kind, grantee_id)"
        " VALUES (%s, %s, %s, 'team', %s)"
    )
    await connection.execute(grant, (workspace.org_id, "knowledge_item", uuid.uuid4(), team))

    with pytest.raises(AppError, match="team_has_knowledge"):
        await found.teams.delete_team(as_owner, team)
    await connection.execute("DELETE FROM resource_grants")
    await connection.execute(grant, (workspace.org_id, "meeting", uuid.uuid4(), team))
    await found.teams.delete_team(as_owner, team)

    assert await fetch_value(connection, "SELECT count(*) FROM resource_grants") == 0


async def test_any_member_starts_a_project_and_only_its_lead_or_an_admin_changes_it(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    found = services(homes, FixedSeats(paid=0))
    owner, member, other, guest = (uuid.uuid4() for _ in range(4))
    workspace = await created(found, HOME, owner)
    for person, role in (
        (member, WorkspaceRole.MEMBER),
        (other, WorkspaceRole.MEMBER),
        (guest, WorkspaceRole.GUEST),
    ):
        await found.admission.admit(
            HOME, Joining(workspace.org_id, person, HOME, role, JoinChannel.DOMAIN)
        )
    scope = {
        person: TenancyScope(HOME, person, workspace.org_id)
        for person in (owner, member, other, guest)
    }

    started = await found.teams.create_project(scope[member], project())
    with pytest.raises(AppError, match="not_allowed"):
        await found.teams.create_project(scope[guest], project())
    with pytest.raises(AppError, match="not_allowed"):
        await found.teams.update_project(scope[other], started, project())
    await found.teams.update_project(scope[owner], started, project())
    await found.teams.delete_project(scope[owner], started)

    connection = run_slot.claimed.connections[HOME]
    assert await fetch_value(connection, "SELECT count(*) FROM projects") == 0
    assert "workspaces.project.deleted" in await event_types(connection)
