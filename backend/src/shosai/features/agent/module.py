"""The agent slice as composition sees it (agent plan §3.1).

Step 1 published the contract, the event and the domain; step 2 added the tables in each
home and the handler of a person's data; step 3 Settings > Leo and its four switches of the
native `/v1/auth/me`; step 4 the threads and their history, with a workspace's threads
following the person's membership; step 5a the run — admitted and streamed by the API, driven
by the workers of the `agent` queue, swept when its worker is lost (AG-D12); step 5b its
context, a thread's title and summary, and the run's telemetry and objectives. The tools, the
Action Gateway and the cabinet's other routes join in the later steps.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts, QueueCompanion
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.application.account_data import ACCOUNT_DATA, AgentAccountData
from shosai.features.agent.application.after_turn import AfterTurn
from shosai.features.agent.application.departures import Departures
from shosai.features.agent.application.fleet_presence import present_in_fleet
from shosai.features.agent.application.history import History
from shosai.features.agent.application.lost_runs import LostRuns
from shosai.features.agent.application.preferences import AgentPreferences
from shosai.features.agent.application.run_context import ContextBuilder
from shosai.features.agent.application.run_engine import EngineParts, RunEngine
from shosai.features.agent.application.run_registry import RunRegistry
from shosai.features.agent.application.run_streams import RunStreams
from shosai.features.agent.application.run_telemetry import RunTelemetry
from shosai.features.agent.application.thread_care import ThreadCare
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.turn_commit import TurnParts
from shosai.features.agent.application.turn_start import TurnStarter
from shosai.features.agent.channels.http.settings import build_settings_router
from shosai.features.agent.channels.http.threads import build_threads_router
from shosai.features.agent.channels.http.turns import build_turns_router
from shosai.features.agent.channels.subscriptions import subscriptions
from shosai.features.agent.channels.tasks import PERIODIC_JOBS, task_handlers
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.log_tail import LogTail
from shosai.features.agent.infrastructure.person_records import PERSON_MODELS
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_metrics import RunMetrics
from shosai.features.agent.infrastructure.run_records import RUN_MODELS
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.thread_records import THREAD_MODELS
from shosai.features.agent.infrastructure.turn_graph import turn_graph
from shosai.features.agent.objectives import AGENT_OBJECTIVES
from shosai.features.agent.settings import AgentSettings, agent_model_set
from shosai.features.identity.contracts import ME_CONTRIBUTIONS

# Трассировщик среза: спаны хода Leo (agent.run, agent.context) без единого слова разговора.
TRACER_NAME = "shosai.agent"


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Settings > Leo, threads and their history, turns and runs, departures, and the
    handler of a person's data."""
    transactions, ports, valkey = services.transactions, services.ports, services.valkey
    preferences = AgentPreferences(transactions)
    threads = Threads(transactions, (ports, services.effects))
    departures = Departures(transactions, ports)
    run_log, leases, fleet = RunLog(valkey), ThreadLeases(valkey), Fleet(valkey)
    tail, registry = LogTail(valkey, run_log), RunRegistry(leases, fleet)
    settings = services.settings.features.get(AgentSettings)
    metrics = RunMetrics(services.registry)
    telemetry = RunTelemetry(metrics, services.tracer_provider.get_tracer(TRACER_NAME))
    engine = RunEngine(
        EngineParts(
            transactions, services.ai, settings.standard_route(), run_log, leases, fleet,
            registry, services.outbox, turn_graph(), ContextBuilder(ports), telemetry,
        )
    )  # fmt: skip
    starter = TurnStarter(
        TurnParts(
            transactions, ports, services.effects, services.rate_limiter, services.tasks,
            run_log, leases, fleet, threads,
        )
    )  # fmt: skip
    streams = RunStreams(transactions, (run_log, tail), leases, metrics)
    lost_runs = LostRuns(transactions, (run_log, leases, fleet), metrics)
    care = ThreadCare(transactions, (services.ai, settings.utility_route()), ports)
    try:
        yield FeatureParts(
            http_routers=(
                build_settings_router(preferences, ports),
                build_threads_router((threads, History(transactions, threads)), ports),
                build_turns_router((starter, streams), ports),
            ),
            task_handlers=task_handlers(departures, lost_runs, engine, care),
            subscriptions=subscriptions(departures, AfterTurn(services.tasks)),
            periodic_jobs=PERIODIC_JOBS,
            queue_companions=(QueueCompanion(TaskQueue.AGENT, lambda: present_in_fleet(fleet)),),
            provides=(
                ACCOUNT_DATA_HANDLERS.bind(AgentAccountData(transactions, valkey)),
                ME_CONTRIBUTIONS.bind(preferences),
            ),
        )
    finally:
        await tail.close()
        await registry.close()


AGENT = FeatureModule(
    name="agent",
    build=build,
    models=(*THREAD_MODELS, *RUN_MODELS, *PERSON_MODELS),
    events=(TurnCompleted,),
    settings=(AgentSettings,),
    production_checks=(agent_model_set,),
    objectives=AGENT_OBJECTIVES,
    account_data=(ACCOUNT_DATA,),
)
