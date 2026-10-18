"""inv-11's reconciliation, the plan change followed at once and the storage route (step 5)."""

import uuid
from datetime import UTC, datetime, timedelta

from prometheus_client import CollectorRegistry
from sqlalchemy.dialects.postgresql import insert

from shosai.core.config.roles import ProcessRole
from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.homes import Home
from shosai.features.billing.contracts.events import SubscriptionChanged
from shosai.features.files.application.quota_reconciliation import QuotaReconciliation
from shosai.features.files.channels.http.storage import build_storage_router
from shosai.features.files.channels.subscriptions import subscriptions
from shosai.features.files.infrastructure.object_deleter import record_deletions
from shosai.features.files.infrastructure.quota_metrics import QuotaMetrics
from shosai.features.files.infrastructure.upload_records import StorageUsageRecord
from shosai.features.identity.contracts import Principal
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.files.file_bench import FileBench
from tests.features.files.test_quota import seed
from tests.features.files.upload_bench import Clock, person
from tests.harness.database_access import ProcessShape, open_database_access, slot_urls
from tests.harness.run_slot import RunSlot

MIB = 1024**2


def plan_changed(who: Principal | None, org_id: uuid.UUID | None = None) -> SubscriptionChanged:
    return SubscriptionChanged(
        subscription_id=uuid.uuid4(), user_id=None if who is None else who.user_id,
        org_id=org_id, plan_slug="free",
    )  # fmt: skip


async def test_the_reconciliation_counts_drifted_counters_and_orphaned_objects(
    file_bench: FileBench, run_slot: RunSlot
) -> None:
    who, drifted = person(Home.RU, uuid.uuid4()), person(Home.RU, uuid.uuid4())
    await file_bench.file(who, "Plan.pdf", b"%PDF" * 40)
    async with file_bench.uploads.transactions.begin(drifted.scope()) as session:
        await session.execute(
            insert(StorageUsageRecord).values(user_id=drifted.user_id, used_bytes=5)
        )
    objects = file_bench.uploads.objects[Home.RU]
    orphan, waiting = (f"u/{who.user_id}/f/{uuid.uuid4()}" for _ in range(2))
    for key in (orphan, waiting):
        await objects.put(key, b"bytes", content_type="application/pdf")
    async with file_bench.uploads.transactions.begin(who.scope()) as session:
        await record_deletions(session, [waiting])
    registry = CollectorRegistry()
    # Через двое суток объекты старше порога в сутки и час.
    later = Clock(datetime.now(UTC) + timedelta(days=2))

    async with open_database_access(
        slot_urls(run_slot), ProcessShape(role=ProcessRole.WORKERS)
    ) as workers:
        found = await QuotaReconciliation(
            workers.transactions, (file_bench.uploads.objects, QuotaMetrics(registry)), later
        ).run(Home.RU)

    assert found == (1, 1)
    assert registry.get_sample_value("shosai_files_quota_drift", {"home": "ru"}) == 1
    assert registry.get_sample_value("shosai_files_orphaned_objects", {"home": "ru"}) == 1


async def test_a_plan_change_marks_at_once_and_a_workspace_plan_is_skipped(
    file_bench: FileBench,
) -> None:
    who = person(Home.EU, uuid.uuid4())
    await seed(file_bench, who, [400 * MIB] * 3)
    [follow_plan] = [
        s
        for s in subscriptions((file_bench.watch, file_bench.leo_watch))
        if s.consumer == "files.quota_follows_plan"
    ]
    now = file_bench.uploads.clock.now

    async with file_bench.uploads.transactions.begin(who.scope()) as session:
        for event in (plan_changed(None, uuid.uuid4()), plan_changed(who)):
            await follow_plan.handle(
                session, ReceivedEvent(event, uuid.uuid4(), 1, now, who.scope())
            )
    standing = await file_bench.watch.standing(Home.EU, who.user_id)

    assert standing.over_limit_since == now
    assert standing.removal_at == now + timedelta(days=90)


async def test_the_storage_route_shows_the_meter_and_answers_503_without_a_plan(
    file_bench: FileBench,
) -> None:
    who = person(Home.RU, uuid.uuid4())
    await seed(file_bench, who, [300])
    watches = (file_bench.watch, file_bench.leo_watch)
    app = build_probe_app(extra=(build_storage_router(watches, file_bench.ports),)).app
    headers = {"Authorization": f"Bearer person:{who.user_id}:{Home.RU.value}"}
    async with client_of(app) as http:
        shown = await http.get("/v1/files/storage", headers=headers)
        file_bench.uploads.plan.unavailable = True
        unknown = await http.get("/v1/files/storage", headers=headers)

    assert shown.json() == {
        "used_bytes": 300, "limit_bytes": 1024**3, "over_limit_since": None, "removal_at": None,
        "leo_used_bytes": 0, "leo_limit_bytes": 100 * MIB, "leo_over_limit_since": None,
        "leo_removal_at": None,
    }  # fmt: skip
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (
        503, "entitlements_unavailable",
    )  # fmt: skip
