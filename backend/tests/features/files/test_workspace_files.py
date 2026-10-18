"""Files and workspaces (step 8a): the transfer, a departed member, a deleted workspace or file."""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from shosai.core.events.domain_event import DomainEvent
from shosai.core.events.subscriptions import EventSubscription, ReceivedEvent
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.files.channels.http.files import build_files_router
from shosai.features.files.channels.subscriptions import subscriptions
from shosai.features.identity.contracts import Principal
from shosai.features.workspaces.channels.file_consumers import DeletedFiles
from shosai.features.workspaces.contracts.events import MemberRemoved, WorkspaceDeleted
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.files.file_bench import FileBench
from tests.features.files.upload_bench import person
from tests.features.workspaces.services import FixedSeats, created, services
from tests.features.workspaces.test_knowledge_transfer import join, share
from tests.harness.connections import Connection, fetch_rows, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

HOME = Home.EU


@dataclass(frozen=True, slots=True)
class Company:
    """Carol in workspaces A (with Bob, owned by Alice) and B (owned by Frank)."""

    alice: Principal
    bob: Principal
    carol: Principal
    frank: Principal
    org_a: uuid.UUID
    org_b: uuid.UUID
    carol_in_a: uuid.UUID
    carol_in_b: uuid.UUID


async def company(homes: DatabaseAccess) -> Company:
    found = services(homes, FixedSeats(paid=10))
    alice, bob, carol, frank = (person(HOME, uuid.uuid4()) for _ in range(4))
    org_a = (await created(found, HOME, alice.user_id)).org_id
    org_b = (await created(found, HOME, frank.user_id)).org_id
    carol_in_a = await join(found, org_a, carol.user_id)
    await join(found, org_a, bob.user_id)
    carol_in_b = await join(found, org_b, carol.user_id)
    return Company(alice, bob, carol, frank, org_a, org_b, carol_in_a, carol_in_b)


async def shared_file(
    bench: FileBench, connection: Connection, people: Company, name: str
) -> uuid.UUID:
    """Carol's file, used by Leo through its own switch, shared into A and B."""
    upload = await bench.uploaded(people.carol, name, b"%PDF" * 100)
    [view] = await bench.manager.register(people.carol, [upload], None, leo=True)
    await share(connection, people.org_a, view.id, people.carol_in_a, "organization")
    await share(connection, people.org_b, view.id, people.carol_in_b, "organization")
    return view.id


async def deliver(
    bench: FileBench,
    subscription: EventSubscription[Any],
    event: DomainEvent,
    scope: TenancyScope,
) -> None:
    """One delivery of the event to the consumer, in the event's scope."""
    async with bench.uploads.transactions.begin(scope) as session:
        received = ReceivedEvent(event, uuid.uuid4(), 1, datetime.now(UTC), scope)
        await subscription.handle(session, received)


def files_consumer(bench: FileBench, name: str) -> EventSubscription[Any]:
    found = subscriptions((bench.watch, bench.leo_watch), bench.outbox)
    [subscription] = [s for s in found if s.consumer == name]
    return subscription


async def items(connection: Connection) -> list[tuple[uuid.UUID, str]]:
    rows = await fetch_rows(
        connection, "SELECT org_id, source_kind FROM workspace_knowledge_items ORDER BY org_id"
    )
    return [(row["org_id"], row["source_kind"]) for row in rows]


async def test_a_transferred_file_leaves_my_files_and_every_other_workspace(
    file_bench: FileBench, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[HOME]
    people = await company(homes)
    file_id = await shared_file(file_bench, connection, people, "Plan.pdf")
    unshared = await file_bench.file(people.carol, "Draft.pdf", b"%PDF" * 10)
    app = build_probe_app(
        extra=(
            build_files_router(
                (file_bench.manager, file_bench.downloads, file_bench.transfers), file_bench.ports
            ),
        )
    ).app
    headers = {"Authorization": f"Bearer person:{people.carol.user_id}:{HOME.value}"}
    into_a = {"workspace_id": str(people.org_a)}
    async with client_of(app) as http:
        refused = await http.post(f"/v1/files/{unshared.id}/transfer", json=into_a, headers=headers)
        handed = await http.post(f"/v1/files/{file_id}/transfer", json=into_a, headers=headers)
        again = await http.post(f"/v1/files/{file_id}/transfer", json=into_a, headers=headers)
        into_b = await http.post(
            f"/v1/files/{file_id}/transfer",
            json={"workspace_id": str(people.org_b)},
            headers=headers,
        )
        listed = (await http.get("/v1/files", headers=headers)).json()

    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "share_first")
    assert (handed.status_code, again.status_code, into_b.status_code) == (204, 204, 404)
    assert [f["id"] for f in listed["files"]] == [str(unshared.id)]
    row = (
        await fetch_rows(
            connection,
            "SELECT user_id, org_id, access, folder_id, leo_on FROM storage_files WHERE id = %s",
            (file_id,),
        )
    )[0]
    assert tuple(row.values()) == (
        people.carol.user_id, people.org_a, "organization", None, False,
    )  # fmt: skip
    assert await items(connection) == [(people.org_a, "upload")]
    assert await file_bench.used(people.carol) == unshared.size_bytes
    audit = "SELECT count(*) FROM org_audit_events WHERE action = 'file_transferred'"
    assert await fetch_value(connection, audit) == 1
    assert (file_id, False) in await file_bench.leo_events(people.carol)
    # Боб читает файл пространства; Фрэнк из B — нет.
    assert (await file_bench.downloads.link(people.bob, file_id)).url
    with pytest.raises(AppError, match="file_not_found"):
        await file_bench.downloads.link(people.frank, file_id)


async def test_a_transfer_and_a_deletion_of_one_file_never_deadlock(
    file_bench: FileBench, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[HOME]
    people = await company(homes)
    file_id = await shared_file(file_bench, connection, people, "Plan.pdf")

    outcomes = await asyncio.gather(
        file_bench.transfers.transfer(people.carol, file_id, people.org_a),
        file_bench.manager.delete(people.carol, file_id),
        return_exceptions=True,
    )

    refused = [o for o in outcomes if isinstance(o, AppError)]
    assert [error.code for error in refused] == ["file_not_found"]
    assert not [o for o in outcomes if isinstance(o, BaseException) and o not in refused]


async def test_a_departed_member_s_workspace_files_pass_to_the_owner_and_her_own_stay(
    file_bench: FileBench, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[HOME]
    people = await company(homes)
    given = await shared_file(file_bench, connection, people, "Plan.pdf")
    own = await shared_file(file_bench, connection, people, "Notes.pdf")
    await file_bench.transfers.transfer(people.carol, given, people.org_a)
    found = services(homes, FixedSeats(paid=10))
    as_alice = TenancyScope(HOME, people.alice.user_id, people.org_a)
    await found.members.remove(as_alice, people.carol_in_a)
    removed = MemberRemoved.model_validate(
        await fetch_value(
            connection,
            "SELECT payload FROM outbox_messages WHERE event_type = 'workspaces.member.removed'",
        )
    )
    consumer = files_consumer(file_bench, "files.follow_departure")

    await deliver(file_bench, consumer, removed, as_alice)
    await deliver(file_bench, consumer, removed, as_alice)

    owners = await fetch_rows(
        connection, "SELECT id, user_id, org_id FROM storage_files ORDER BY name"
    )
    assert [tuple(row.values()) for row in owners] == [
        (own, people.carol.user_id, None),
        (given, people.alice.user_id, people.org_a),
    ]
    # Личный файл Кэрол ушёл из A вместе с ней и остался в B.
    assert (people.org_a, "personal") not in await items(connection)
    assert (people.org_b, "personal") in await items(connection)


async def test_a_deleted_workspace_s_files_go_and_only_their_orphaned_objects_with_them(
    file_bench: FileBench, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[HOME]
    people = await company(homes)
    kept = await shared_file(file_bench, connection, people, "Plan.pdf")
    lost = await shared_file(file_bench, connection, people, "Notes.pdf")
    copy = await file_bench.manager.copy(people.carol, kept, None)
    for file_id in (kept, lost):
        await file_bench.transfers.transfer(people.carol, file_id, people.org_a)
    keys = {
        row["id"]: row["object_key"]
        for row in await fetch_rows(connection, "SELECT id, object_key FROM storage_files")
    }
    consumer = files_consumer(file_bench, "files.erase_with_workspace")
    scope = TenancyScope(HOME, org_id=people.org_a)

    await deliver(file_bench, consumer, WorkspaceDeleted(org_id=people.org_a), scope)
    await deliver(file_bench, consumer, WorkspaceDeleted(org_id=people.org_a), scope)
    await file_bench.uploads.deleter.retry(HOME)

    left = await fetch_rows(connection, "SELECT id FROM storage_files")
    assert [row["id"] for row in left] == [copy.id]
    objects = file_bench.uploads.objects[HOME]
    assert await objects.head(keys[kept]) is not None
    assert await objects.head(keys[lost]) is None
    erased = await fetch_rows(
        connection,
        "SELECT payload FROM outbox_messages WHERE event_type = 'files.file.deleted'",
    )
    assert sorted(row["payload"]["file_id"] for row in erased) == sorted([str(kept), str(lost)])


async def test_a_deleted_file_leaves_every_workspace_it_was_shared_in(
    file_bench: FileBench, homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[HOME]
    people = await company(homes)
    file_id = await shared_file(file_bench, connection, people, "Plan.pdf")
    await file_bench.manager.delete(people.carol, file_id)
    deleted = await fetch_value(
        connection, "SELECT payload FROM outbox_messages WHERE event_type = 'files.file.deleted'"
    )
    [consumer] = DeletedFiles(file_bench.outbox).subscriptions()
    event = consumer.event.model_validate(deleted)
    scope = TenancyScope(HOME, people.carol.user_id)

    await deliver(file_bench, consumer, event, scope)
    await deliver(file_bench, consumer, event, scope)

    assert await items(connection) == []
    grants = "SELECT count(*) FROM resource_grants WHERE resource_kind = 'knowledge_item'"
    assert await fetch_value(connection, grants) == 0
    removed = "SELECT count(*) FROM outbox_messages WHERE event_type LIKE '%knowledge_item.removed'"
    assert await fetch_value(connection, removed) == 2
