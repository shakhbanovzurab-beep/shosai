"""The memory slice as composition sees it (memory plan §3.1).

Step 1 published the domain — facts and their changes, the trust of a fact, decay, what
reaches a turn, admission, lifetimes, the summary and the "Ask or update" box — the texts the
models read, and the agent's ports memory binds and uses. Step 2 added the tables in each
home, the `vector` extension and the handler of what memory holds of a person. Step 3 the
routes of Settings > Memory's facts and switch, and the switch's mirror in the native
`/v1/auth/me`. Step 4 the vectors — the embedding pass once a minute per home on the owner's
`google/gemini-embedding-2` — and the agent's `MEMORY_RECALL` and `PROFILE_FACTS` bound.
Admission and the toolset come with the plan's next steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.agent.contracts.memory import MEMORY_RECALL, PROFILE_FACTS
from shosai.features.identity.contracts import ME_CONTRIBUTIONS
from shosai.features.memory.application.account_data import ACCOUNT_DATA, MemoryAccountData
from shosai.features.memory.application.embedding_pass import EmbeddingPass
from shosai.features.memory.application.fact_changes import FactChanges
from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.recall import Recall
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.channels.http.facts import build_memory_router
from shosai.features.memory.channels.tasks import PERIODIC_JOBS, embedding_tick
from shosai.features.memory.infrastructure.embeddings import Embedder
from shosai.features.memory.infrastructure.metrics import MemoryMetrics
from shosai.features.memory.infrastructure.records import MEMORY_MODELS
from shosai.features.memory.settings import MemorySettings


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Memory's parts for this process."""
    transactions, ports = services.transactions, services.ports
    lists = FactLists(transactions, ports)
    changes = FactChanges(transactions, (lists, services.effects, services.valkey))
    switch = MemorySwitch(transactions)
    settings = services.settings.features.get(MemorySettings)
    embedder = Embedder(services.ai, settings.embedding_route())
    metrics = MemoryMetrics(services.registry)
    recall = Recall(transactions, (lists, embedder, services.valkey, metrics))
    embedding = EmbeddingPass(transactions, (ports, embedder, services.valkey, metrics))
    yield FeatureParts(
        http_routers=(build_memory_router((lists, changes, switch), ports),),
        task_handlers=(embedding_tick(embedding),),
        periodic_jobs=PERIODIC_JOBS,
        provides=(
            ACCOUNT_DATA_HANDLERS.bind(MemoryAccountData(transactions, services.valkey)),
            ME_CONTRIBUTIONS.bind(switch),
            MEMORY_RECALL.bind(recall),
            PROFILE_FACTS.bind(recall),
        ),
    )


MEMORY = FeatureModule(
    name="memory",
    build=build,
    models=MEMORY_MODELS,
    settings=(MemorySettings,),
    account_data=(ACCOUNT_DATA,),
)
