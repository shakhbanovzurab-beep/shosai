"""The agent slice as composition sees it (agent plan §3.1).

Step 1 published the contract, the event and the domain; step 2 added the tables in each
home and the handler of a person's data. The settings, the threads, the run on the `agent`
queue, the tools, the Action Gateway and the cabinet's routes join in the later steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.agent.application.account_data import ACCOUNT_DATA, AgentAccountData
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.infrastructure.person_records import PERSON_MODELS
from shosai.features.agent.infrastructure.run_records import RUN_MODELS
from shosai.features.agent.infrastructure.thread_records import THREAD_MODELS


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The handler of a person's data."""
    handler = AgentAccountData(services.transactions, services.valkey)
    yield FeatureParts(provides=(ACCOUNT_DATA_HANDLERS.bind(handler),))


AGENT = FeatureModule(
    name="agent",
    build=build,
    models=(*THREAD_MODELS, *RUN_MODELS, *PERSON_MODELS),
    events=(TurnCompleted,),
    account_data=(ACCOUNT_DATA,),
)
