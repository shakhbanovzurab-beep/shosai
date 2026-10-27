"""The catalogue's daily refresh from OpenRouter's list (ST-D4 as amended, ADR 0074)."""

from collections.abc import Mapping

import httpx
from prometheus_client import CollectorRegistry
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.studio.application.catalogue_refresh import CatalogueRefresh
from shosai.features.studio.domain.roles import ModelRole
from shosai.features.studio.infrastructure.metrics import RefreshOutcome, StudioMetrics
from shosai.features.studio.infrastructure.platform_records import CatalogueRecord
from tests.features.studio.catalogue_bench import (
    LINE,
    CatalogueBench,
    catalogue_bench,
    entry,
    openrouter_list,
    price,
)
from tests.harness.connections import fetch_rows
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

FLASH, MINI, SONNET, HAIKU = (
    "google/gemini-3.8-flash",
    "openai/gpt-6-mini",
    "anthropic/claude-sonnet-5",
    "anthropic/claude-haiku-5.5",
)
ALL = (FLASH, MINI, SONNET, HAIKU)


def refresher(bench: CatalogueBench, registry: CollectorRegistry) -> CatalogueRefresh:
    """The refresh over the bench's list, outbox and snapshot."""
    sources = (bench.listing, bench.outbox, bench.snapshot, StudioMetrics(registry))
    return CatalogueRefresh(bench.homes.transactions, sources, LINE)


async def seeded(homes: DatabaseAccess) -> CatalogueBench:
    """Four models listed and switched on; Leo's default is Flash."""
    bench = catalogue_bench(homes)
    every = openrouter_list(*(entry(model, image=True) for model in ALL))
    for model in ALL:
        bench.lists(every)
        added = await bench.admin.add(model)
        await bench.admin.switch(added.id, enabled=True)
    await bench.admin.set_default(ModelRole.LEO, "google-gemini-3-8-flash")
    return bench


async def rows(homes: DatabaseAccess) -> Mapping[str, CatalogueRecord]:
    """The catalogue's rows by id."""
    async with homes.transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
        return {row.id: row for row in (await session.scalars(select(CatalogueRecord))).all()}


async def events(run_slot: RunSlot) -> list[tuple[str, str]]:
    """The outbox's studio events: type and model."""
    found = await fetch_rows(
        run_slot.claimed.connections[Home.EU],
        "SELECT event_type, payload->>'model_id' AS model FROM outbox_messages"
        " ORDER BY occurred_at",
        (),
    )
    return [(row["event_type"], row["model"]) for row in found]


def counted(registry: CollectorRegistry, name: str, **labels: str) -> float:
    """A counter's value in the registry."""
    return registry.get_sample_value(name, labels) or 0.0


async def test_a_vanished_model_is_switched_off_once_and_a_default_only_counted(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await seeded(homes)
    registry = CollectorRegistry()
    refresh = refresher(bench, registry)
    without = openrouter_list(entry(SONNET, image=True), entry(HAIKU, image=True))
    bench.lists(without, without)

    outcomes = [await refresh.refresh(), await refresh.refresh()]
    found = await rows(homes)

    assert outcomes == [RefreshOutcome.DONE, RefreshOutcome.DONE]
    assert found["openai-gpt-6-mini"].enabled is False
    assert found["openai-gpt-6-mini"].upstream_missing_since is not None
    assert found["google-gemini-3-8-flash"].enabled is True
    assert await events(run_slot) == [("studio.model.disabled", "openai-gpt-6-mini")]
    assert counted(registry, "shosai_studio_broken_defaults_total", reason="unlisted") == 2


async def test_a_list_missing_much_of_the_catalogue_switches_nothing_off(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await seeded(homes)
    registry = CollectorRegistry()
    bench.lists(openrouter_list(entry(SONNET, image=True)), httpx.Response(500))

    refresh = refresher(bench, registry)
    outcome = await refresh.refresh()
    unreadable = await refresh.refresh()

    assert (outcome, unreadable) == (RefreshOutcome.FUSED, RefreshOutcome.UNREADABLE)
    assert all(row.enabled for row in (await rows(homes)).values())
    assert await events(run_slot) == []


async def test_a_price_across_the_line_proposes_a_tier_once_and_changes_nothing(
    homes: DatabaseAccess, run_slot: RunSlot
) -> None:
    bench = await seeded(homes)
    await price(homes, MINI, "0.00002")
    refresh = refresher(bench, CollectorRegistry())
    every = openrouter_list(*(entry(model, image=True, reasoning=True) for model in ALL))
    bench.lists(every, every)

    await refresh.refresh()
    await refresh.refresh()
    mini = (await rows(homes))["openai-gpt-6-mini"]

    assert (mini.tier, mini.tier_proposed, mini.supports_reasoning) == (
        "standard",
        "frontier",
        True,
    )
    assert await events(run_slot) == [("studio.model.tier_proposed", "openai-gpt-6-mini")]


async def test_a_model_back_on_the_list_is_not_switched_on_again(homes: DatabaseAccess) -> None:
    bench = await seeded(homes)
    refresh = refresher(bench, CollectorRegistry())
    bench.lists(
        openrouter_list(*(entry(model, image=True) for model in (FLASH, SONNET, HAIKU))),
        openrouter_list(*(entry(model, image=True) for model in ALL)),
    )

    await refresh.refresh()
    await refresh.refresh()
    mini = (await rows(homes))["openai-gpt-6-mini"]

    assert (mini.enabled, mini.upstream_missing_since) == (False, None)
