"""The memory slice as composition sees it (memory plan §3.1).

Step 1 published the domain — facts and their changes, the trust of a fact, decay, what
reaches a turn, admission, lifetimes, the summary and the "Ask or update" box — the texts the
models read, and the agent's ports memory binds and uses. Step 2 added the tables in each
home, the `vector` extension and the handler of what memory holds of a person. Routes,
recall, admission and the toolset come with the plan's next steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.memory.application.account_data import ACCOUNT_DATA, MemoryAccountData
from shosai.features.memory.infrastructure.records import MEMORY_MODELS


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Memory's parts for this process."""
    handler = MemoryAccountData(services.transactions, services.valkey)
    yield FeatureParts(provides=(ACCOUNT_DATA_HANDLERS.bind(handler),))


MEMORY = FeatureModule(
    name="memory",
    build=build,
    models=MEMORY_MODELS,
    account_data=(ACCOUNT_DATA,),
)
