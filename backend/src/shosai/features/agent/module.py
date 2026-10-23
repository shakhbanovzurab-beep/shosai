"""The agent slice as composition sees it (agent plan §3.1).

Step 1 published the contract, the event and the domain; step 2 added the tables in each
home and the handler of a person's data; step 3 Settings > Leo and its four switches of the
native `/v1/auth/me`; step 4 the threads and their history, with a workspace's threads
following the person's membership. The run on the `agent` queue, the tools, the Action
Gateway and the cabinet's other routes join in the later steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.agent.application.account_data import ACCOUNT_DATA, AgentAccountData
from shosai.features.agent.application.departures import Departures
from shosai.features.agent.application.history import History
from shosai.features.agent.application.preferences import AgentPreferences
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.channels.http.settings import build_settings_router
from shosai.features.agent.channels.http.threads import build_threads_router
from shosai.features.agent.channels.subscriptions import subscriptions
from shosai.features.agent.channels.tasks import PERIODIC_JOBS, task_handlers
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.infrastructure.person_records import PERSON_MODELS
from shosai.features.agent.infrastructure.run_records import RUN_MODELS
from shosai.features.agent.infrastructure.thread_records import THREAD_MODELS
from shosai.features.identity.contracts import ME_CONTRIBUTIONS


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Settings > Leo with its native switches, the threads with their history and departures,
    and the handler of a person's data."""
    transactions, ports = services.transactions, services.ports
    preferences = AgentPreferences(transactions)
    handler = AgentAccountData(transactions, services.valkey)
    threads = Threads(transactions, (ports, services.effects))
    departures = Departures(transactions, ports)
    yield FeatureParts(
        http_routers=(
            build_settings_router(preferences, ports),
            build_threads_router((threads, History(transactions, threads)), ports),
        ),
        task_handlers=task_handlers(departures),
        subscriptions=subscriptions(departures),
        periodic_jobs=PERIODIC_JOBS,
        provides=(
            ACCOUNT_DATA_HANDLERS.bind(handler),
            ME_CONTRIBUTIONS.bind(preferences),
        ),
    )


AGENT = FeatureModule(
    name="agent",
    build=build,
    models=(*THREAD_MODELS, *RUN_MODELS, *PERSON_MODELS),
    events=(TurnCompleted,),
    account_data=(ACCOUNT_DATA,),
)
