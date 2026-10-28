"""The studio slice as composition sees it (studio plan §3.1, ADR 0074).

Step 1 published the contracts — `MODEL_ROUTES`, `MODEL_CATALOGUE`, `PROMPT_RESOLVER` and the
two events — and the domain: roles, the catalogue and the tier a price proposes, defaults per
role, the resolution of a model, a person's prompts, skills and context, the platform layer
and its versions. Step 2 the tables — the platform's in the EU home, a person's in each —
and the handler of what studio holds of a person. Step 3a the catalogue: models added from
OpenRouter's list, switched, retired, their tier decided, defaults per role under row locks,
the process's snapshot and `MODEL_CATALOGUE`. Step 3b the daily refresh from OpenRouter's
list. Step 4 Admin > AI models on `/v1/admin/ai-models*`. Step 6 the platform layer: its
draft, publish, versions and restore on `/v1/admin/platform-prompts*`, and the published layer
in the snapshot. Step 8 the person's Studio on `/v1/studio/*` — the context, prompts with
their skills, the prompt per role, the models on the plan and the role settings — and the
consumer that takes an uninstalled skill off the prompts. Step 10 the resolution for people:
`MODEL_ROUTES` with billing's allowance inside the route, and `PROMPT_RESOLVER` with the
platform layer, a person's role prompt and their context.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.studio.application.account_data import ACCOUNT_DATA, StudioAccountData
from shosai.features.studio.application.ai_models_screen import AiModelsScreen
from shosai.features.studio.application.catalogue_admin import CatalogueAdmin
from shosai.features.studio.application.catalogue_refresh import CatalogueRefresh
from shosai.features.studio.application.model_routes import StudioModelRoutes
from shosai.features.studio.application.offers import CatalogueOffers
from shosai.features.studio.application.person_prompts import PersonPrompts
from shosai.features.studio.application.person_settings import PersonSettings
from shosai.features.studio.application.platform_prompts import PlatformPrompts
from shosai.features.studio.application.platform_reader import PlatformPromptReader
from shosai.features.studio.application.prompt_resolver import StudioPromptResolver
from shosai.features.studio.channels.http.admin_ai_models import build_admin_ai_models_router
from shosai.features.studio.channels.http.admin_platform_prompts import (
    build_admin_platform_prompts_router,
)
from shosai.features.studio.channels.http.studio_routes import build_studio_router
from shosai.features.studio.channels.subscriptions import SUBSCRIPTIONS
from shosai.features.studio.channels.tasks import PERIODIC_JOBS, refresh_tick
from shosai.features.studio.contracts import MODEL_CATALOGUE, MODEL_ROUTES, PROMPT_RESOLVER
from shosai.features.studio.contracts.events import STUDIO_EVENTS
from shosai.features.studio.infrastructure.metrics import StudioMetrics
from shosai.features.studio.infrastructure.person_records import PERSON_MODELS
from shosai.features.studio.infrastructure.platform_records import PLATFORM_MODELS
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot
from shosai.features.studio.infrastructure.route_metrics import RouteMetrics
from shosai.features.studio.settings import StudioSettings


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Studio's parts for this process."""
    snapshot = PlatformSnapshot(services.transactions, services.registry)
    settings = services.settings.features.get(StudioSettings)
    line = settings.studio_frontier_output_usd_per_m
    sources = (services.ai_listing, services.outbox, snapshot)
    refresh = CatalogueRefresh(
        services.transactions, (*sources, StudioMetrics(services.registry)), line
    )
    admin = CatalogueAdmin(services.transactions, sources, line)
    screen = AiModelsScreen(
        services.transactions,
        (services.ai_spend.reports, services.ai_spend.credits, services.ai_listing),
        services.settings.ai.openrouter_api_key,
    )
    prompts = PlatformPrompts(services.transactions, (services.effects, snapshot))
    metrics = RouteMetrics(services.registry)
    resolver = StudioPromptResolver(PlatformPromptReader(snapshot), services.ports, metrics)
    person = (
        PersonPrompts(services.transactions, (services.effects, services.ports)),
        PersonSettings(services.transactions, (snapshot, services.ports)),
    )
    yield FeatureParts(
        http_routers=(
            build_admin_ai_models_router((admin, screen), services.ports),
            build_admin_platform_prompts_router(prompts, services.ports),
            build_studio_router(person, services.ports),
        ),
        task_handlers=(refresh_tick(refresh),),
        subscriptions=SUBSCRIPTIONS,
        periodic_jobs=PERIODIC_JOBS,
        provides=(
            ACCOUNT_DATA_HANDLERS.bind(StudioAccountData(services.transactions)),
            MODEL_CATALOGUE.bind(CatalogueOffers(snapshot)),
            MODEL_ROUTES.bind(StudioModelRoutes(snapshot, services.ports, metrics)),
            PROMPT_RESOLVER.bind(resolver),
        ),
    )


STUDIO = FeatureModule(
    name="studio",
    build=build,
    models=(*PLATFORM_MODELS, *PERSON_MODELS),
    events=STUDIO_EVENTS,
    settings=(StudioSettings,),
    account_data=(ACCOUNT_DATA,),
)
