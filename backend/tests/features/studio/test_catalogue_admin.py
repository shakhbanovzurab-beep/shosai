"""The operator's catalogue: models from OpenRouter's list, switches, tiers and defaults under
row locks, the snapshot and the models a person is offered (ST-D3, ST-D4, ADR 0074)."""

import asyncio
from collections.abc import Awaitable

import httpx
import pytest
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.studio.application.offers import CatalogueOffers
from shosai.features.studio.domain.errors import StudioRule, StudioRuleError
from shosai.features.studio.domain.roles import ModelCapability, ModelRole, Tier
from shosai.features.studio.domain.routing import Substitution
from shosai.features.studio.infrastructure.platform_records import CatalogueRecord
from tests.features.studio.catalogue_bench import (
    CatalogueBench,
    catalogue_bench,
    entry,
    openrouter_list,
    person,
    price,
)
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

SONNET, FLASH = "anthropic/claude-sonnet-5", "google/gemini-3.8-flash"


async def listed(bench: CatalogueBench, *ids: str) -> None:
    """Add these models from one list, each switched on."""
    for model_id in ids:
        bench.lists(openrouter_list(*(entry(item, image=True) for item in ids)))
        model = await bench.admin.add(model_id)
        await bench.admin.switch(model.id, enabled=True)


async def refused(rule: StudioRule, call: Awaitable[object]) -> None:
    """The awaited call breaks the rule."""
    with pytest.raises(StudioRuleError) as raised:
        await call
    assert raised.value.rule is rule


async def test_a_model_is_described_by_openrouter_priced_into_its_tier_and_starts_off(
    homes: DatabaseAccess,
) -> None:
    bench = catalogue_bench(homes)
    await price(homes, SONNET, "0.000015")
    bench.lists(openrouter_list(entry(SONNET, image=True, reasoning=True)))

    model = await bench.admin.add(SONNET)

    assert (model.id, model.maker, model.name) == (
        "anthropic-claude-sonnet-5",
        "Maker",
        "Claude-Sonnet-5",
    )
    assert model.tier is Tier.FRONTIER
    assert model.capabilities == {ModelCapability.TEXT, ModelCapability.VISION}
    assert (model.supports_reasoning, model.enabled, model.max_output_tokens) == (
        True,
        False,
        32_000,
    )


async def test_adding_refuses_what_openrouter_does_not_list_and_what_is_listed_already(
    homes: DatabaseAccess,
) -> None:
    bench = catalogue_bench(homes)
    bench.lists(openrouter_list(entry(FLASH)), openrouter_list(entry(FLASH)), httpx.Response(503))

    await bench.admin.add(FLASH)

    await refused(StudioRule.MODEL_ALREADY_LISTED, bench.admin.add(FLASH))
    await refused(StudioRule.OPENROUTER_UNREACHABLE, bench.admin.add(SONNET))
    bench.lists(openrouter_list(entry(FLASH)))
    await refused(StudioRule.MODEL_NOT_ON_OPENROUTER, bench.admin.add(SONNET))


async def test_two_ids_with_one_plain_slug_both_get_listed(homes: DatabaseAccess) -> None:
    bench = catalogue_bench(homes)
    first, second = "maker/model.1", "maker/model-1"
    bench.lists(*(openrouter_list(entry(first), entry(second)) for _ in range(2)))

    ids = {(await bench.admin.add(first)).id, (await bench.admin.add(second)).id}

    assert len(ids) == 2
    assert "maker-model-1" in ids


async def test_a_default_holds_its_model_on_listed_standard_and_able(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = catalogue_bench(homes)
    await listed(bench, FLASH, SONNET)
    flash, sonnet = "google-gemini-3-8-flash", "anthropic-claude-sonnet-5"

    await bench.admin.set_default(ModelRole.LEO, flash, sonnet)

    await refused(StudioRule.MODEL_IS_DEFAULT, bench.admin.switch(sonnet, enabled=False))
    await refused(StudioRule.MODEL_ENABLED, bench.admin.retire(flash))
    await bench.admin.set_default(ModelRole.LEO, flash)
    await bench.admin.switch(sonnet, enabled=False)
    await refused(StudioRule.MODEL_DISABLED, bench.admin.set_default(ModelRole.CODE, sonnet))
    await bench.admin.retire(sonnet)
    await refused(StudioRule.MODEL_NOT_FOUND, bench.admin.set_default(ModelRole.CODE, sonnet))
    events = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT event_type, payload->>'model_id' AS model FROM outbox_messages",
        (),
    )
    assert [(row["event_type"], row["model"]) for row in events] == [
        ("studio.model.disabled", sonnet)
    ]


async def test_concurrent_writes_never_leave_a_default_the_rules_refuse(
    homes: DatabaseAccess,
) -> None:
    bench = catalogue_bench(homes)
    await listed(bench, FLASH)
    flash = "google-gemini-3-8-flash"

    for _ in range(10):
        results = await asyncio.gather(
            bench.admin.set_default(ModelRole.CODE, flash),
            bench.admin.switch(flash, enabled=False),
            return_exceptions=True,
        )
        defaults = await bench.admin.defaults()
        async with homes.transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
            enabled = await session.scalar(
                select(CatalogueRecord.enabled).where(CatalogueRecord.id == flash)
            )
        assert enabled or all(default.model_id != flash for default in defaults), results
        if not enabled:
            await bench.admin.switch(flash, enabled=True)


async def test_a_tier_waits_for_the_admin_who_may_not_make_a_default_frontier(
    homes: DatabaseAccess,
) -> None:
    bench = catalogue_bench(homes)
    await listed(bench, FLASH)
    flash = "google-gemini-3-8-flash"
    await bench.admin.set_default(ModelRole.NOTES, flash)

    await refused(StudioRule.NO_TIER_PROPOSAL, bench.admin.decide_tier(flash, confirm=True))
    async with homes.transactions.begin(TenancyScope(Home.EU)) as session:
        record = await session.get(CatalogueRecord, flash)
        assert record is not None
        record.tier_proposed, record.tier_proposed_at = "frontier", record.updated_at
    await refused(StudioRule.MODEL_IS_DEFAULT, bench.admin.decide_tier(flash, confirm=True))

    kept = await bench.admin.decide_tier(flash, confirm=False)

    assert (kept.tier, kept.tier_proposed, kept.tier_declined) == (
        Tier.STANDARD,
        None,
        Tier.FRONTIER,
    )


async def test_another_process_reads_a_change_within_its_snapshot_and_offers_by_plan(
    homes: DatabaseAccess,
) -> None:
    bench = catalogue_bench(homes)
    other = bench.other_process()
    await price(homes, SONNET, "0.000015")
    await listed(bench, FLASH, SONNET)
    offers = CatalogueOffers(bench.snapshot)
    assert len((await other.catalogue()).models) == 2

    await bench.admin.switch("google-gemini-3-8-flash", enabled=False)
    stale = (await other.catalogue()).models["google-gemini-3-8-flash"].enabled
    other.drop()
    fresh = (await other.catalogue()).models["google-gemini-3-8-flash"].enabled

    assert (stale, fresh) == (True, False)
    assert [model.id for model in await offers.offered(person(frontier=True))] == [
        "anthropic-claude-sonnet-5"
    ]
    assert await offers.offered(person()) == ()
    assert (
        await offers.refusal(person(), "anthropic-claude-sonnet-5", ModelRole.CODE)
        is Substitution.NOT_ON_PLAN
    )
