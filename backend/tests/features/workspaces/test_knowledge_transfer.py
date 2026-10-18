"""Handing a shared file over to a workspace: workspaces' `KnowledgeTransfer` port (step 9a)."""

import asyncio
import uuid
from dataclasses import dataclass
from http import HTTPStatus

import pytest

from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.application.access_policy import WorkspaceAccessPolicy
from shosai.features.workspaces.application.admission import Joining
from shosai.features.workspaces.application.knowledge_transfer import (
    TransferScopeMismatchError,
    WorkspaceKnowledgeTransfer,
)
from shosai.features.workspaces.application.teams import TeamDraft
from shosai.features.workspaces.contracts import AccessLevel, TransferredFile, Viewer
from shosai.features.workspaces.contracts.events import JoinChannel
from shosai.features.workspaces.domain.roles import WorkspaceRole
from shosai.features.workspaces.infrastructure.audit_log import WorkspaceAuditLog
from shosai.features.workspaces.module import WORKSPACES
from tests.features.workspaces.probe_resources import FILES
from tests.features.workspaces.services import (
    FixedSeats,
    Services,
    audit_actions,
    created,
    event_types,
    services,
)
from tests.harness.connections import Connection, fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

HOME = Home.EU


@dataclass(frozen=True, slots=True)
class Shared:
    """Carol's file shared into A for a team and into B for everyone; Bob is in the team."""

    org_a: uuid.UUID
    org_b: uuid.UUID
    alice: uuid.UUID
    bob: uuid.UUID
    carol: uuid.UUID
    frank: uuid.UUID
    team: uuid.UUID
    carol_in_a: uuid.UUID
    file_id: uuid.UUID
    item_a: uuid.UUID
    item_b: uuid.UUID


def transfer_port() -> WorkspaceKnowledgeTransfer:
    return WorkspaceKnowledgeTransfer(
        EventOutbox(EventTypes(list(WORKSPACES.events))), WorkspaceAuditLog()
    )


def policy() -> WorkspaceAccessPolicy:
    return WorkspaceAccessPolicy(
        EventOutbox(EventTypes(list(WORKSPACES.events))), WorkspaceAuditLog()
    )


async def join(found: Services, org_id: uuid.UUID, person: uuid.UUID) -> uuid.UUID:
    joining = Joining(org_id, person, HOME, WorkspaceRole.MEMBER, JoinChannel.DOMAIN)
    return await found.admission.admit(HOME, joining)


async def share(
    connection: Connection, org_id: uuid.UUID, file_id: uuid.UUID, sharer: uuid.UUID, access: str
) -> uuid.UUID:
    """A personal item of the file, as the publish route will write it, with the adder's grant."""
    item = uuid.uuid4()
    await connection.execute(
        "INSERT INTO workspace_knowledge_items"
        " (id, org_id, source_kind, file_id, access, added_by_membership_id)"
        " VALUES (%s, %s, 'personal', %s, %s, %s)",
        (item, org_id, file_id, access, sharer),
    )
    await grant(connection, org_id, item, "member", sharer)
    return item


async def grant(
    connection: Connection, org_id: uuid.UUID, item: uuid.UUID, kind: str, grantee: uuid.UUID
) -> None:
    await connection.execute(
        "INSERT INTO resource_grants (org_id, resource_kind, resource_id, grantee_kind, grantee_id)"
        " VALUES (%s, 'knowledge_item', %s, %s, %s)",
        (org_id, item, kind, grantee),
    )


async def shared_file(homes: DatabaseAccess, run_slot: RunSlot) -> Shared:
    found = services(homes, FixedSeats(paid=10))
    alice, bob, carol, frank = (uuid.uuid4() for _ in range(4))
    a = (await created(found, HOME, alice)).org_id
    b = (await created(found, HOME, frank)).org_id
    carol_in_a, bob_in_a, carol_in_b = (
        await join(found, a, carol),
        await join(found, a, bob),
        await join(found, b, carol),
    )
    draft = TeamDraft("Core", "", "violet", private=True, member_ids=frozenset({bob_in_a}))
    team = await found.teams.create_team(TenancyScope(HOME, alice, a), draft)
    connection = run_slot.claimed.connections[HOME]
    file_id = uuid.uuid4()
    await connection.execute(
        "INSERT INTO probe_files (id, user_id) VALUES (%s, %s)", (file_id, carol)
    )
    item_a = await share(connection, a, file_id, carol_in_a, "selected")
    await grant(connection, a, item_a, "team", team)
    item_b = await share(connection, b, file_id, carol_in_b, "organization")
    await connection.execute("DELETE FROM outbox_messages")
    await connection.execute("DELETE FROM org_audit_events")
    return Shared(a, b, alice, bob, carol, frank, team, carol_in_a, file_id, item_a, item_b)


async def readers(homes: DatabaseAccess, shared: Shared) -> set[uuid.UUID]:
    """Who of the four may read the file now, through the policy and row-level security."""
    found = set()
    for person in (shared.alice, shared.bob, shared.carol, shared.frank):
        async with homes.transactions.begin(TenancyScope(HOME, person), read_only=True) as session:
            ids = await policy().filter_readable(session, FILES, [shared.file_id], Viewer(person))
        if ids:
            found.add(person)
    return found


async def transfer(
    homes: DatabaseAccess, shared: Shared, org_id: uuid.UUID, *, adopt: bool = True
) -> TransferredFile:
    """The transfer as files' route will run it: the port, then the file joins the workspace."""
    scope = TenancyScope(HOME, shared.carol, org_id)
    async with homes.transactions.begin(scope) as session:
        result = await transfer_port().transfer(session, org_id, shared.file_id, shared.carol)
        if adopt:
            await session.execute(
                FILES.table.update()
                .where(FILES.table.c.id == shared.file_id)
                .values(org_id=org_id, access=result.level)
            )
    return result


async def test_the_file_becomes_the_workspace_upload_read_by_the_same_people(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    shared = await shared_file(homes, run_slot)
    connection = run_slot.claimed.connections[HOME]
    assert await readers(homes, shared) == {shared.bob, shared.carol, shared.frank}

    result = await transfer(homes, shared, shared.org_a)

    assert result == TransferredFile(shared.item_a, AccessLevel.SELECTED)
    items = await fetch_rows(
        connection, "SELECT id, source_kind FROM workspace_knowledge_items ORDER BY id"
    )
    assert [(row["id"], row["source_kind"]) for row in items] == [(shared.item_a, "upload")]
    grants = await fetch_rows(
        connection, "SELECT resource_kind, resource_id, grantee_kind FROM resource_grants"
    )
    assert sorted((g["resource_kind"], g["resource_id"], g["grantee_kind"]) for g in grants) == [
        ("file", shared.file_id, "member"),
        ("file", shared.file_id, "team"),
    ]
    # Команда Боба и Кэрол читают файл пространства; Фрэнк в B его больше не видит.
    assert await readers(homes, shared) == {shared.bob, shared.carol}
    assert await audit_actions(connection) == ["file_transferred"]
    audit = await fetch_rows(
        connection,
        "SELECT org_id, actor_membership_id, target_kind, target_id FROM org_audit_events",
    )
    assert [tuple(row.values()) for row in audit] == [
        (shared.org_a, shared.carol_in_a, "file", shared.file_id)
    ]
    assert await event_types(connection) == ["workspaces.knowledge_item.removed"]
    payload = await fetch_value(connection, "SELECT payload FROM outbox_messages")
    assert payload == {"org_id": str(shared.org_b), "item_id": str(shared.item_b)}


async def test_a_file_not_shared_there_by_its_owner_is_refused_and_nothing_changes(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    shared = await shared_file(homes, run_slot)
    connection = run_slot.claimed.connections[HOME]
    await connection.execute(
        "DELETE FROM workspace_knowledge_items WHERE id = %s", (shared.item_a,)
    )
    before = await fetch_rows(connection, "SELECT * FROM workspace_knowledge_items ORDER BY id")

    with pytest.raises(AppError, match="share_first") as refused:
        await transfer(homes, shared, shared.org_a, adopt=False)
    stranger = TenancyScope(HOME, shared.alice, shared.org_b)
    with pytest.raises(AppError, match="workspace_not_found"):
        async with homes.transactions.begin(stranger) as session:
            await transfer_port().transfer(session, shared.org_b, shared.file_id, shared.alice)
    with pytest.raises(TransferScopeMismatchError):
        async with homes.transactions.begin(TenancyScope(HOME, shared.carol)) as session:
            await transfer_port().transfer(session, shared.org_b, shared.file_id, shared.carol)

    assert refused.value.status == HTTPStatus.CONFLICT
    assert await fetch_rows(connection, "SELECT * FROM workspace_knowledge_items ORDER BY id") == (
        before
    )
    assert await audit_actions(connection) == []
    assert await event_types(connection) == []


async def test_a_repeat_answers_the_same_item_and_writes_nothing_more(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    shared = await shared_file(homes, run_slot)
    connection = run_slot.claimed.connections[HOME]

    first = await transfer(homes, shared, shared.org_a)
    again = await transfer(homes, shared, shared.org_a, adopt=False)

    assert again == first
    assert await audit_actions(connection) == ["file_transferred"]
    assert await event_types(connection) == ["workspaces.knowledge_item.removed"]


async def test_two_transfers_of_one_file_hand_it_to_one_workspace_without_a_deadlock(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    shared = await shared_file(homes, run_slot)
    connection = run_slot.claimed.connections[HOME]

    outcomes = await asyncio.gather(
        transfer(homes, shared, shared.org_a),
        transfer(homes, shared, shared.org_b),
        return_exceptions=True,
    )

    won = [o for o in outcomes if isinstance(o, TransferredFile)]
    refused = [o for o in outcomes if isinstance(o, AppError)]
    assert len(won) == 1
    assert [error.code for error in refused] == ["share_first"]
    kept = await fetch_rows(connection, "SELECT id, source_kind FROM workspace_knowledge_items")
    assert [(row["id"], row["source_kind"]) for row in kept] == [(won[0].item_id, "upload")]
    assert await audit_actions(connection) == ["file_transferred"]


async def test_a_team_holding_a_transferred_file_is_not_deleted(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    shared = await shared_file(homes, run_slot)
    await transfer(homes, shared, shared.org_a)
    found = services(homes, FixedSeats(paid=10))

    with pytest.raises(AppError, match="team_has_knowledge"):
        await found.teams.delete_team(TenancyScope(HOME, shared.alice, shared.org_a), shared.team)
