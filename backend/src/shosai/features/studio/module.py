"""The studio slice as composition sees it (studio plan §3.1, ADR 0074).

Step 1 published the contracts — `MODEL_ROUTES`, `MODEL_CATALOGUE`, `PROMPT_RESOLVER` and the
two events — and the domain: roles, the catalogue and the tier a price proposes, defaults per
role, the resolution of a model, a person's prompts, skills and context, the platform layer
and its versions. Step 2 the tables — the platform's in the EU home, a person's in each —
and the handler of what studio holds of a person. Step 3a the catalogue: models added from
OpenRouter's list, switched, retired, their tier decided, defaults per role under row locks,
the process's snapshot and `MODEL_CATALOGUE`. Step 3b the daily refresh from OpenRouter's
list. `MODEL_ROUTES` and `PROMPT_RESOLVER` are bound with the resolution (step 10).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.studio.application.account_data import ACCOUNT_DATA, StudioAccountData
from shosai.features.studio.application.catalogue_refresh import CatalogueRefresh
from shosai.features.studio.application.offers import CatalogueOffers
from shosai.features.studio.channels.tasks import PERIODIC_JOBS, refresh_tick
from shosai.features.studio.contracts import MODEL_CATALOGUE
from shosai.features.studio.contracts.events import STUDIO_EVENTS
from shosai.features.studio.infrastructure.metrics import StudioMetrics
from shosai.features.studio.infrastructure.person_records import PERSON_MODELS
from shosai.features.studio.infrastructure.platform_records import PLATFORM_MODELS
from shosai.features.studio.infrastructure.platform_snapshot import PlatformSnapshot
from shosai.features.studio.settings import StudioSettings


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Studio's parts for this process."""
    snapshot = PlatformSnapshot(services.transactions, services.registry)
    settings = services.settings.features.get(StudioSettings)
    refresh = CatalogueRefresh(
        services.transactions,
        (services.ai_listing, services.outbox, snapshot, StudioMetrics(services.registry)),
        settings.studio_frontier_output_usd_per_m,
    )
    yield FeatureParts(
        task_handlers=(refresh_tick(refresh),),
        periodic_jobs=PERIODIC_JOBS,
        provides=(
            ACCOUNT_DATA_HANDLERS.bind(StudioAccountData(services.transactions)),
            MODEL_CATALOGUE.bind(CatalogueOffers(snapshot)),
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
