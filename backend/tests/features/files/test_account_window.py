"""Identity's deletion window (files step 7, ADR 0045 point 6): a hidden account's files are
served to nobody — its owner, a workspace they are shared in, Leo, a download, the daily
passes — and a cancellation shows them again, unchanged; events out of order end where the
latest one says.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from shosai.core.events.records import OutboxMessage
from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.files.application.visibility import visible_files
from shosai.features.files.channels.subscriptions import subscriptions
from shosai.features.files.domain.leo import bytes_in_use
from shosai.features.files.infrastructure.file_records import FILE_RESOURCE, StorageFileRecord
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from shosai.features.identity.channels.subscriptions import audit_operator_action
from shosai.features.identity.contracts import (
    AccountDeletionCancelled,
    AccountDeletionScheduled,
    OperatorActed,
    Principal,
)
from shosai.features.workspaces.contracts import ACCESS_POLICY, Viewer
from shosai.features.workspaces.infrastructure.share_records import SHARE_RECORDS
from tests.features.files.file_bench import FileBench
from tests.features.files.upload_bench import person
from tests.harness.connections import fetch_rows
from tests.harness.run_slot import RunSlot
from tests.support.access_model import MemberRow, ResourceRow, ShareRow, WorkspaceRow, World
from tests.support.isolation import write_world

SIZE = 10_000
# Лимит места ниже файла: вне окна удаления ежедневный шаг квоты ставит отметку.
LIMIT = 1_000


async def shared_file(
    bench: FileBench, run_slot: RunSlot, owner: Principal, member: Principal
) -> uuid.UUID:
    """A personal file of `owner`, starred and Leo on, shared into a workspace both belong
    to; the owner's counter holds it."""
    file_id, org_id, owner_seat, member_seat = (uuid.uuid4() for _ in range(4))
    records = SHARE_RECORDS["file"]
    world = World(
        workspaces=[WorkspaceRow(org_id, "active")],
        members=[
            MemberRow(owner_seat, org_id, owner.user_id, "owner", "active"),
            MemberRow(member_seat, org_id, member.user_id, "member", "active"),
        ],
        rows=[ResourceRow(file_id, "file", owner.user_id, None, None)],
        shares=[
            ShareRow(
                "file", file_id, org_id, "organization", owner_seat, records.grant_kind,
                uuid.uuid4(),
            )
        ],
    )  # fmt: skip
    extra = {
        "name": "Plan.txt", "content_type": "text/plain", "size_bytes": SIZE,
        "object_key": f"u/{owner.user_id}/f/{file_id}", "leo_on": True, "starred": True,
    }  # fmt: skip
    await write_world(run_slot.claimed.connections[owner.home], FILE_RESOURCE, world, extra)
    async with bench.uploads.transactions.begin(owner.scope()) as session:
        await session.execute(
            insert(StorageUsageRecord).values(user_id=owner.user_id, used_bytes=SIZE)
        )
    return file_id


async def seen_by(bench: FileBench, viewer: Principal) -> set[uuid.UUID]:
    """The files the viewer's read path admits."""
    policy = bench.ports.get(ACCESS_POLICY)
    async with bench.uploads.transactions.begin(viewer.scope(), read_only=True) as session:
        return set(
            await session.scalars(
                visible_files(policy, Viewer(viewer.user_id)).with_only_columns(
                    StorageFileRecord.id
                )
            )
        )


async def deliver(
    bench: FileBench,
    who: Principal,
    event: AccountDeletionScheduled | AccountDeletionCancelled,
    at: datetime,
) -> None:
    """One delivery of an identity event to its files consumer, in the person's scope."""
    consumer = "files.hide_with_account" if hidden(event) else "files.show_with_account"
    [subscription] = [
        s for s in subscriptions((bench.watch, bench.leo_watch)) if s.consumer == consumer
    ]
    async with bench.uploads.transactions.begin(who.scope()) as session:
        received = ReceivedEvent(event, uuid.uuid4(), 1, at, who.scope())
        await subscription.handle(session, received)


def hidden(event: AccountDeletionScheduled | AccountDeletionCancelled) -> bool:
    return isinstance(event, AccountDeletionScheduled)


async def test_a_hidden_account_s_files_are_served_to_nobody_and_come_back_unchanged(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    owner, member = person(Home.RU, uuid.uuid4()), person(Home.RU, uuid.uuid4())
    file_id = await shared_file(file_bench, run_slot, owner, member)
    before = (await seen_by(file_bench, owner), await seen_by(file_bench, member))
    async with file_bench.uploads.transactions.begin(owner.scope(), read_only=True) as session:
        leo_before = bytes_in_use(await file_bench.leo.in_use(session, owner.user_id))
    scheduled_at = datetime.now(UTC)
    scheduled = AccountDeletionScheduled(
        user_id=owner.user_id, erase_at=scheduled_at + timedelta(days=7)
    )

    await deliver(file_bench, owner, scheduled, scheduled_at)
    during = (await seen_by(file_bench, owner), await seen_by(file_bench, member))
    _, listed = await file_bench.manager.listing(owner)
    async with file_bench.uploads.transactions.begin(owner.scope(), read_only=True) as session:
        leo_bytes = bytes_in_use(await file_bench.leo.in_use(session, owner.user_id))
    refused = []
    for viewer in (owner, member):
        with pytest.raises(AppError, match="file_not_found"):
            await file_bench.downloads.link(viewer, file_id)
        refused.append(viewer.user_id)
    quota_step = await file_bench.watch.step(Home.RU, owner.user_id, LIMIT)
    await deliver(
        file_bench,
        owner,
        AccountDeletionCancelled(user_id=owner.user_id),
        scheduled_at + timedelta(hours=1),
    )
    _, [back] = await file_bench.manager.listing(owner)

    assert (before, leo_before) == (({file_id}, {file_id}), SIZE)
    assert during == (set(), set())
    assert (listed, leo_bytes, len(refused), quota_step) == ([], 0, 2, None)
    assert (back.id, back.starred, back.leo is not None) == (file_id, True, True)
    assert await seen_by(file_bench, member) == {file_id}
    assert await file_bench.watch.step(Home.RU, owner.user_id, LIMIT) is not None


async def test_window_events_out_of_order_end_where_the_latest_says_and_a_repeat_changes_nothing(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    owner, member = person(Home.EU, uuid.uuid4()), person(Home.EU, uuid.uuid4())
    file_id = await shared_file(file_bench, run_slot, owner, member)
    start = datetime.now(UTC)
    scheduled = AccountDeletionScheduled(user_id=owner.user_id, erase_at=start + timedelta(days=7))
    cancelled = AccountDeletionCancelled(user_id=owner.user_id)

    await deliver(file_bench, owner, scheduled, start + timedelta(minutes=2))
    await deliver(file_bench, owner, cancelled, start + timedelta(minutes=1))
    late_cancel = await seen_by(file_bench, member)
    await deliver(file_bench, owner, cancelled, start + timedelta(minutes=3))
    await deliver(file_bench, owner, scheduled, start + timedelta(minutes=2))
    async with file_bench.uploads.transactions.begin(owner.scope(), read_only=True) as session:
        row = await session.scalar(
            select(StorageUsageRecord).where(StorageUsageRecord.user_id == owner.user_id)
        )

    assert late_cancel == set()
    assert await seen_by(file_bench, member) == {file_id}
    assert row is not None
    assert (row.account_hidden, row.account_event_at) == (False, start + timedelta(minutes=3))


async def audit_rows(
    bench: FileBench, run_slot: RunSlot, who: Principal
) -> list[tuple[str, uuid.UUID | None]]:
    """The person's audit events, delivered to identity's EU log as its consumer does; the
    log's rows as (action, file)."""
    async with bench.uploads.transactions.begin(who.scope(), read_only=True) as session:
        found = list(
            await session.execute(
                select(OutboxMessage.id, OutboxMessage.occurred_at, OutboxMessage.payload)
                .where(OutboxMessage.event_type == OperatorActed.event_type)
                .order_by(OutboxMessage.id)
            )
        )
    for event_id, occurred_at, payload in found:
        received = ReceivedEvent(
            OperatorActed.model_validate(payload), event_id, 1, occurred_at, who.scope()
        )
        async with bench.uploads.transactions.begin(TenancyScope(Home.EU)) as session:
            await audit_operator_action(session, received)
    rows = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT action, subject_id FROM operator_audit_events"
        " WHERE target_user_id = %s ORDER BY created_at",
        (who.user_id,),
    )
    return [(row["action"], row["subject_id"]) for row in rows]


async def test_support_neither_sees_nor_restores_a_hidden_account_s_files_and_is_audited(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    owner, member = person(Home.RU, uuid.uuid4()), person(Home.RU, uuid.uuid4())
    file_id = await shared_file(file_bench, run_slot, owner, member)
    await file_bench.manager.delete(owner, file_id)
    start = datetime.now(UTC)
    scheduled = AccountDeletionScheduled(user_id=owner.user_id, erase_at=start + timedelta(days=7))

    await deliver(file_bench, owner, scheduled, start)
    refused = []
    for call in (
        file_bench.support.of_person(Home.RU, owner.user_id),
        file_bench.support.restore(Home.RU, owner.user_id, file_id),
    ):
        with pytest.raises(AppError, match="account_deletion_scheduled"):
            await call
        refused.append(True)
    await deliver(
        file_bench,
        owner,
        AccountDeletionCancelled(user_id=owner.user_id),
        start + timedelta(minutes=1),
    )
    [listed] = await file_bench.support.of_person(Home.RU, owner.user_id)
    await file_bench.support.restore(Home.RU, owner.user_id, file_id)
    _, [back] = await file_bench.manager.listing(owner)

    assert refused == [True, True]
    assert (listed.file_id, back.id) == (file_id, file_id)
    assert await audit_rows(file_bench, run_slot, owner) == [
        ("files_listed", None), ("file_restored", file_id),
    ]  # fmt: skip
