"""The memory slice as composition sees it (memory plan §3.1).

Step 1 published the domain — facts and their changes, the trust of a fact, decay, what
reaches a turn, admission, lifetimes, the summary and the "Ask or update" box — the texts the
models read, and the agent's ports memory binds and uses. Step 2 added the tables in each
home, the `vector` extension and the handler of what memory holds of a person. Step 3 the
routes of Settings > Memory's facts and switch, and the switch's mirror in the native
`/v1/auth/me`. Step 4 the vectors — the embedding pass once a minute per home on the owner's
`google/gemini-embedding-2` — and the agent's `MEMORY_RECALL` and `PROFILE_FACTS` bound.
Step 5 a turn's admission after `agent.turn.completed`. Step 6 Leo's `memory` toolset —
`memory.recall` and `memory.forget` — offered while the person's memory is on. Step 7 the
summary, its "Ask or update" box and restore. Step 9 a meeting's recollection after its first
notes. Step 8 the daily upkeep, the facts that follow their sources and the invariant's check.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.core.idempotency.action_items import ActionItems
from shosai.features.agent.contracts.memory import MEMORY_RECALL, PROFILE_FACTS
from shosai.features.identity.contracts import ME_CONTRIBUTIONS
from shosai.features.memory.application.account_data import ACCOUNT_DATA, MemoryAccountData
from shosai.features.memory.application.box_messages import BoxMessages
from shosai.features.memory.application.departures import Departures
from shosai.features.memory.application.embedding_pass import EmbeddingPass
from shosai.features.memory.application.fact_changes import FactChanges
from shosai.features.memory.application.fact_forgets import FactForgets
from shosai.features.memory.application.fact_list import FactLists
from shosai.features.memory.application.fact_restore import FactRestore
from shosai.features.memory.application.fact_search import FactSearch
from shosai.features.memory.application.invariants import MemoryInvariants
from shosai.features.memory.application.meeting_recollection import MeetingRecollection
from shosai.features.memory.application.recall import Recall
from shosai.features.memory.application.summaries import Summaries
from shosai.features.memory.application.summary_facts import SummaryFacts
from shosai.features.memory.application.switch import MemorySwitch
from shosai.features.memory.application.turn_admission import TurnAdmission
from shosai.features.memory.application.upkeep import Upkeep
from shosai.features.memory.channels.agent_tool_handlers import MemoryTools
from shosai.features.memory.channels.agent_tools import MEMORY_TOOLS
from shosai.features.memory.channels.departure_events import departure_subscriptions
from shosai.features.memory.channels.http.facts import build_memory_router
from shosai.features.memory.channels.http.summary import build_summary_router
from shosai.features.memory.channels.subscriptions import subscriptions
from shosai.features.memory.channels.tasks import (
    PERIODIC_JOBS,
    embedding_tick,
    meeting_recollection,
    summary_queue,
    summary_writes,
    turn_admission,
    upkeep_ticks,
)
from shosai.features.memory.infrastructure.embeddings import Embedder
from shosai.features.memory.infrastructure.extractor import Extractor
from shosai.features.memory.infrastructure.memory_model import MemoryModel
from shosai.features.memory.infrastructure.metrics import MemoryMetrics
from shosai.features.memory.infrastructure.recollector import Recollector
from shosai.features.memory.infrastructure.records import MEMORY_MODELS
from shosai.features.memory.infrastructure.summary_model import SummaryModel
from shosai.features.memory.settings import MemorySettings


def summary_parts(
    services: CoreServices, lists: FactLists, metrics: MemoryMetrics, settings: MemorySettings
) -> tuple[Summaries, BoxMessages]:
    """The summary and its box on memory's model."""
    model = SummaryModel(MemoryModel(services.ai, settings.model_route()))
    held = SummaryFacts(lists)
    summaries = Summaries(
        services.transactions,
        (held, model, services.ports, metrics),
        (summary_queue(services.tasks), services.valkey),
    )
    box = BoxMessages(
        services.transactions,
        (lists, held, model, summaries),
        (services.effects, services.rate_limiter, services.valkey, services.ports),
    )
    return summaries, box


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
    admission = TurnAdmission(
        transactions,
        (Extractor(services.ai, settings.model_route()), embedder),
        (ports, services.effects, services.valkey, metrics),
    )
    recollection = MeetingRecollection(
        transactions,
        (Recollector(services.ai, settings.model_route()), embedder),
        (ports, services.effects, metrics),
    )
    search = FactSearch(transactions, (lists, embedder, services.valkey, ports))
    items = ActionItems(services.effects, services.outbox)
    tools = MemoryTools(transactions, (search, FactForgets(lists), items))
    summaries, box = summary_parts(services, lists, metrics, settings)
    departures = Departures(transactions, (ports, metrics))
    upkeep = Upkeep(transactions, (summaries, services.valkey, metrics))
    restore = FactRestore(transactions, (lists, services.valkey))
    yield FeatureParts(
        http_routers=(
            build_summary_router((summaries, box), ports, services.rate_limiter),
            build_memory_router((lists, changes, switch, restore), ports),
        ),
        agent_tools=tools.bound(),
        task_handlers=(
            embedding_tick(embedding),
            turn_admission(admission),
            summary_writes(summaries),
            meeting_recollection(recollection),
            *upkeep_ticks(upkeep, departures, MemoryInvariants(transactions, metrics)),
        ),
        subscriptions=(*subscriptions(services.tasks), *departure_subscriptions(departures)),
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
    agent_tools=MEMORY_TOOLS,
)
