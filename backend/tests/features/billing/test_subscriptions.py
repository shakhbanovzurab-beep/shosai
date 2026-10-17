"""Subscriptions and the cached `Entitlements` (billing step 3)."""

from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from shosai.core.kernel.homes import Home
from shosai.features.billing.application.catalogue import Catalogue
from shosai.features.billing.contracts import EntitlementsUnavailableError
from shosai.features.billing.domain.plans import FREE_PLAN_ID
from shosai.features.billing.infrastructure.plan_holders import SubscriptionHolders
from tests.features.billing.catalogue_bench import created, plan_draft
from tests.features.billing.entitlement_bench import EntitlementBench

PLANS = "/v1/admin/plans"


async def pro_plan(bench: EntitlementBench, slug: str = "pro") -> tuple[str, str]:
    """A paid plan of the catalogue: its id and slug."""
    return await created(bench.catalogue, PLANS, plan_draft(slug)), slug


async def test_a_change_bumps_the_version_and_the_next_read_sees_it(
    entitlements: EntitlementBench,
) -> None:
    person = (Home.RU, uuid4())
    plan = await pro_plan(entitlements)

    before = await entitlements.snapshots.snapshot(*person)
    cached = await entitlements.without_database().snapshot(*person)
    version = await entitlements.subscribe(person, plan)
    after = await entitlements.snapshots.snapshot(*person)

    assert (before.plan_slug, before.version, before.paid) == ("free", 0, False)
    assert cached == before
    assert (version, after.version) == (1, 1)
    assert (after.plan_slug, after.paid, after.limits.file_manager_gb) == ("pro", True, 100)
    assert after.paid_until == entitlements.clock.now + timedelta(days=30)
    again = await entitlements.subscribe(person, plan, lasting=timedelta(days=60))
    assert again == 2
    assert (await entitlements.snapshots.snapshot(*person)).version == 2


async def test_without_the_database_a_cached_snapshot_serves_and_no_cache_is_503(
    entitlements: EntitlementBench,
) -> None:
    known, unknown = (Home.EU, uuid4()), (Home.EU, uuid4())
    await entitlements.snapshots.snapshot(*known)
    offline = entitlements.without_database()

    served = await offline.snapshot(*known)
    with pytest.raises(EntitlementsUnavailableError) as refused:
        await offline.snapshot(*unknown)

    assert served.plan_slug == "free"
    assert (refused.value.status, refused.value.code) == (503, "entitlements_unavailable")


async def test_a_reader_that_saw_the_old_version_never_stores_it(
    entitlements: EntitlementBench,
) -> None:
    person = (Home.RU, uuid4())
    plan = await pro_plan(entitlements)
    stale = await entitlements.snapshots.entry(*person)
    await entitlements.subscribe(person, plan)

    stored = await entitlements.cache.store(stale, entitlements.clock.now)
    reading = await entitlements.cache.read(person[1])

    assert stored is False
    assert reading.entry is None


async def test_a_catalogue_edit_reaches_cached_snapshots(entitlements: EntitlementBench) -> None:
    person = (Home.EU, uuid4())
    plan = await pro_plan(entitlements)
    await entitlements.subscribe(person, plan)
    first = await entitlements.snapshots.snapshot(*person)
    catalogue = Catalogue(
        entitlements.homes.transactions,
        (SubscriptionHolders(entitlements.homes.transactions), entitlements.cache),
    )

    await catalogue.change(
        UUID(plan[0]),
        lambda current: replace(current, limits=replace(current.limits, file_manager_gb=500)),
    )
    second = await entitlements.snapshots.snapshot(*person)

    assert (first.limits.file_manager_gb, second.limits.file_manager_gb) == (100, 500)
    assert second.version == first.version


async def test_a_queued_plan_takes_over_at_the_expiry_and_the_cache_follows_time(
    entitlements: EntitlementBench,
) -> None:
    person = (Home.RU, uuid4())
    pro = await pro_plan(entitlements)
    queued = await pro_plan(entitlements, "start")
    await entitlements.subscribe(
        person, pro, lasting=timedelta(days=2), queued=((UUID(queued[0]), 3),)
    )

    now = await entitlements.snapshots.snapshot(*person)
    entitlements.clock.advance(timedelta(days=2, minutes=1))
    later = await entitlements.snapshots.snapshot(*person)
    entitlements.clock.advance(timedelta(days=3))
    lapsed = await entitlements.snapshots.snapshot(*person)

    assert [now.plan_slug, later.plan_slug, lapsed.plan_slug] == ["pro", "start", "free"]
    assert lapsed.paid is False


async def test_a_held_plan_is_counted_in_both_homes_and_archived_instead_of_deleted(
    entitlements: EntitlementBench,
) -> None:
    plan = await pro_plan(entitlements)
    await entitlements.subscribe((Home.RU, uuid4()), plan)
    await entitlements.subscribe((Home.EU, uuid4()), plan, lasting=timedelta(hours=23))
    await entitlements.subscribe((Home.EU, uuid4()), plan, lasting=timedelta(hours=-12))
    holders = SubscriptionHolders(entitlements.homes.transactions)
    catalogue = Catalogue(entitlements.homes.transactions, (holders, entitlements.cache))

    counted = await holders.counts([UUID(plan[0]), FREE_PLAN_ID])
    removal = await catalogue.remove(UUID(plan[0]))

    assert counted[UUID(plan[0])].referenced == 3
    assert counted[UUID(plan[0])].current == 2
    assert FREE_PLAN_ID not in counted
    assert removal.result.value == "archived"
    assert removal.plan is not None
    assert removal.plan.subscribers == 2
