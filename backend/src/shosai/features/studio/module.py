"""The studio slice as composition sees it (studio plan §3.1, ADR 0074).

Step 1 published the contracts — `MODEL_ROUTES`, `MODEL_CATALOGUE`, `PROMPT_RESOLVER` and the
two events — and the domain: roles, the catalogue and the tier a price proposes, defaults per
role, the resolution of a model, a person's prompts, skills and context, the platform layer
and its versions. Step 2 the tables — the platform's in the EU home, a person's in each —
and the handler of what studio holds of a person. The ports are bound with the resolution
(step 10).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.studio.application.account_data import ACCOUNT_DATA, StudioAccountData
from shosai.features.studio.contracts.events import STUDIO_EVENTS
from shosai.features.studio.infrastructure.person_records import PERSON_MODELS
from shosai.features.studio.infrastructure.platform_records import PLATFORM_MODELS


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Studio's parts for this process."""
    yield FeatureParts(
        provides=(ACCOUNT_DATA_HANDLERS.bind(StudioAccountData(services.transactions)),),
    )


STUDIO = FeatureModule(
    name="studio",
    build=build,
    models=(*PLATFORM_MODELS, *PERSON_MODELS),
    events=STUDIO_EVENTS,
    account_data=(ACCOUNT_DATA,),
)
