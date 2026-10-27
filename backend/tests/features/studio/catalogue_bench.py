"""The catalogue's bench: a scripted OpenRouter list, prices in force, the admin and a person."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

import httpx
from prometheus_client import CollectorRegistry

from shosai.core.ai.adapters.openrouter import OPENROUTER_API
from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.listing import ModelListing, OpenRouterModels
from shosai.core.ai.pricing.prices import PriceBook
from shosai.core.events.catalog import EventTypes
from shosai.core.events.domain_event import DomainEvent
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.homes import Home
from shosai.features.billing.contracts import (
    Audience,
    Capability,
    EntitlementSnapshot,
    EntitlementSource,
    PlanLimits,
)
from shosai.features.studio.application.catalogue_admin import CatalogueAdmin
from shosai.features.studio.contracts import RoutePerson
from shosai.features.studio.contracts.events import STUDIO_EVENTS
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot
from tests.core.ai.bench import set_prices
from tests.doubles.openrouter import ScriptedOpenRouter
from tests.harness.database_access import DatabaseAccess

LINE = Decimal(6)
NO_CACHE = timedelta(0)


def entry(model_id: str, *, image: bool = False, reasoning: bool = False) -> dict[str, Any]:
    """One model of OpenRouter's list, as the list writes it."""
    inputs = ["text", "image"] if image else ["text"]
    parameters = ["temperature", "tools", *(["reasoning"] if reasoning else [])]
    return {
        "id": model_id, "name": f"Maker: {model_id.rsplit('/', maxsplit=1)[-1].title()}",
        "context_length": 200_000, "top_provider": {"max_completion_tokens": 32_000},
        "architecture": {"input_modalities": inputs, "output_modalities": ["text"]},
        "supported_parameters": parameters,
    }  # fmt: skip


def openrouter_list(*entries: dict[str, Any]) -> httpx.Response:
    """OpenRouter's answer to the model list."""
    return httpx.Response(200, json={"data": list(entries)})


def person(*, frontier: bool = False) -> RoutePerson:
    """A person on a paid plan, with frontier models or without."""
    user_id = uuid.uuid4()
    capabilities = frozenset({Capability.FRONTIER_MODELS}) if frontier else frozenset()
    snapshot = EntitlementSnapshot(
        user_id=user_id, plan_slug="pro", plan_name="Pro", audience=Audience.INDIVIDUAL,
        paid=True, in_grace=False, paid_until=None, limits=PlanLimits(None, None, None),
        capabilities=capabilities, source=EntitlementSource.PERSONAL, workspace_id=None,
        version=1,
    )  # fmt: skip
    return RoutePerson(Home.RU, user_id, snapshot)


async def price(homes: DatabaseAccess, model_id: str, output: str) -> None:
    """An output and input price in force for an OpenRouter model."""
    await set_prices(
        homes.transactions,
        ModelRef(Provider.OPENROUTER, model_id),
        input_token="0.000001",
        output_token=output,
    )


@dataclass
class CatalogueBench:
    """The admin over a scripted list, with its snapshot and the outbox it writes to."""

    homes: DatabaseAccess
    openrouter: ScriptedOpenRouter
    snapshot: PlatformSnapshot
    admin: CatalogueAdmin

    def lists(self, *responses: httpx.Response) -> None:
        """Queue OpenRouter's next answers to the model list."""
        for response in responses:
            self.openrouter.answer("models", response)

    def other_process(self) -> PlatformSnapshot:
        """Another process's snapshot of the same homes."""
        return PlatformSnapshot(self.homes.transactions, CollectorRegistry())


def catalogue_bench(
    homes: DatabaseAccess, events: Sequence[type[DomainEvent]] = STUDIO_EVENTS
) -> CatalogueBench:
    """A bench whose list is read afresh on every call."""
    openrouter = ScriptedOpenRouter()
    models = OpenRouterModels(openrouter.client(), OPENROUTER_API, ttl=NO_CACHE)
    listing = ModelListing(models, PriceBook(homes.transactions, ttl=NO_CACHE))
    snapshot = PlatformSnapshot(homes.transactions, CollectorRegistry())
    outbox = EventOutbox(EventTypes(list(events)))
    admin = CatalogueAdmin(homes.transactions, (listing, outbox, snapshot), LINE)
    return CatalogueBench(homes, openrouter, snapshot, admin)
