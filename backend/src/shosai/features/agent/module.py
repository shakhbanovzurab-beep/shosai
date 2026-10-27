"""The agent slice as composition sees it (agent plan §3.1).

Step 1 published the contract, the event and the domain; step 2 added the tables in each
home and the handler of a person's data; step 3 Settings > Leo and its four switches of the
native `/v1/auth/me`; step 4 the threads and their history, with a workspace's threads
following the person's membership; step 5a the run — admitted and streamed by the API, driven
by the workers of the `agent` queue, swept when its worker is lost (AG-D12); step 5b its
context, a thread's title and summary, and the run's telemetry and objectives; step 6 the
tools — Leo's own `core` toolset, the routing of every slice's toolsets and the rounds that
call them. The Action Gateway and the cabinet's other routes join in the later steps.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

import httpx

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.agent_tools.bindings import AgentTool
from shosai.core.config.roles import ProcessRole
from shosai.core.db.engines import DATABASE_PROFILES
from shosai.core.documents.extraction import DocumentReader
from shosai.core.features import CoreServices, FeatureModule, FeatureParts, QueueCompanion
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.application.account_data import ACCOUNT_DATA, AgentAccountData
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_decisions import ActionDecisions
from shosai.features.agent.application.action_execution import ActionExecution
from shosai.features.agent.application.action_inbox import ActionInbox
from shosai.features.agent.application.action_invariants import ActionInvariants
from shosai.features.agent.application.action_proposal import ActionProposer
from shosai.features.agent.application.action_sweeps import ActionSweeps
from shosai.features.agent.application.after_turn import AfterTurn
from shosai.features.agent.application.case_care import CasePurge
from shosai.features.agent.application.departures import Departures
from shosai.features.agent.application.egress_calls import EgressCalls
from shosai.features.agent.application.feedback import Feedback
from shosai.features.agent.application.fleet_presence import present_in_fleet
from shosai.features.agent.application.friction_judging import FrictionJudging
from shosai.features.agent.application.history import History
from shosai.features.agent.application.installed_skills import InstalledSkills
from shosai.features.agent.application.lost_runs import LostRuns
from shosai.features.agent.application.native_proxy import NativeProxy
from shosai.features.agent.application.paused_runs import PausedRuns
from shosai.features.agent.application.platform_ratings import PlatformRatings
from shosai.features.agent.application.preferences import AgentPreferences
from shosai.features.agent.application.proposal_port import PortProposals
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.application.run_attachments import AttachmentReader
from shosai.features.agent.application.run_context import ContextBuilder
from shosai.features.agent.application.run_engine import RunEngine
from shosai.features.agent.application.run_engine_parts import EngineParts
from shosai.features.agent.application.run_registry import RunRegistry
from shosai.features.agent.application.run_sources import RunSources
from shosai.features.agent.application.run_streams import RunStreams
from shosai.features.agent.application.run_telemetry import RunTelemetry
from shosai.features.agent.application.skill_store import SkillStore
from shosai.features.agent.application.thread_care import ThreadCare
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.tool_offer import TurnRouting
from shosai.features.agent.application.tool_registry import ToolRegistry
from shosai.features.agent.application.tool_round import ToolParts
from shosai.features.agent.application.turn_commit import TurnParts
from shosai.features.agent.application.turn_start import TurnStarter
from shosai.features.agent.channels.agent_tools import CORE_TOOLS, core_tools
from shosai.features.agent.channels.http.actions import build_actions_router
from shosai.features.agent.channels.http.callers import operator_mount, person_mount
from shosai.features.agent.channels.http.feedback import build_feedback_router
from shosai.features.agent.channels.http.native_proxy import build_native_proxy_router
from shosai.features.agent.channels.http.settings import build_settings_router
from shosai.features.agent.channels.http.skills import build_skills_router
from shosai.features.agent.channels.http.threads import build_threads_router
from shosai.features.agent.channels.http.turns import build_turns_router
from shosai.features.agent.channels.platform_reads import PlatformReads
from shosai.features.agent.channels.platform_specs import PLATFORM_TOOLS
from shosai.features.agent.channels.platform_tools import platform_tools
from shosai.features.agent.channels.subscriptions import subscriptions
from shosai.features.agent.channels.tasks import PERIODIC_JOBS, Handlers, task_handlers
from shosai.features.agent.channels.web_tools import WEB_TOOLS, web_tools
from shosai.features.agent.contracts import ACTION_PROPOSALS, SKILL_READER
from shosai.features.agent.contracts.events import TurnCompleted
from shosai.features.agent.infrastructure.action_metrics import ActionMetrics
from shosai.features.agent.infrastructure.feedback_metrics import FeedbackMetrics
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.github_skills import GitHubSkills, github_client
from shosai.features.agent.infrastructure.log_tail import LogTail
from shosai.features.agent.infrastructure.person_records import PERSON_MODELS
from shosai.features.agent.infrastructure.proxy_metrics import ProxyMetrics
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_metrics import RunMetrics
from shosai.features.agent.infrastructure.run_records import RUN_MODELS
from shosai.features.agent.infrastructure.skill_metrics import SkillMetrics
from shosai.features.agent.infrastructure.skills_directory import SkillsDirectory, directory_client
from shosai.features.agent.infrastructure.thread_lease import ThreadLeases
from shosai.features.agent.infrastructure.thread_records import THREAD_MODELS
from shosai.features.agent.infrastructure.tool_metrics import ToolMetrics
from shosai.features.agent.infrastructure.turn_graph import turn_graph
from shosai.features.agent.infrastructure.turn_saver import TurnSaver
from shosai.features.agent.objectives import AGENT_MONITORS, AGENT_OBJECTIVES, AGENT_TRACKED
from shosai.features.agent.settings import AgentSettings, agent_model_set
from shosai.features.identity.contracts import ME_CONTRIBUTIONS

# Трассировщик среза: спаны хода Leo (agent.run, agent.context) без единого слова разговора.
TRACER_NAME = "shosai.agent"
# Одно соединение пула дома остаётся ходам: контекст, раунды и конец прогона.
SPARE_CONNECTIONS: Final = 1


def tool_bulkhead(role: ProcessRole) -> asyncio.Semaphore:
    """How many tool calls of this process run at once: below its pool of connections."""
    profile = DATABASE_PROFILES.get(role) or DATABASE_PROFILES[ProcessRole.WORKERS]
    return asyncio.Semaphore(max(profile.pool_size - SPARE_CONNECTIONS, 1))


def card_proposer(services: CoreServices, cards: ActionCards) -> ActionProposer:
    """The proposer of cards, with a bound friction judge beside the rule."""
    transactions = services.transactions
    judging = FrictionJudging(services.ports, cards, transactions)
    return ActionProposer(transactions, cards, judging=judging)


def action_gateway(
    services: CoreServices,
    cards: ActionCards,
    keys: tuple[RunLog, TurnSaver],
    pages: ResultPages,
) -> tuple[ActionDecisions, tuple[ActionExecution, ActionSweeps, ActionInvariants]]:
    """The Action Gateway: decisions, the executor, the sweeps and the invariants, over one
    settler of paused runs."""
    transactions = services.transactions
    paused = PausedRuns((transactions, services.outbox), keys, (services.tasks, cards))
    metrics = ActionMetrics(services.registry)
    executor = ActionExecution(
        transactions, (services.agent_tools, paused, metrics, EgressCalls(pages))
    )
    judging = FrictionJudging(services.ports, cards, transactions)
    parts = (services.tasks, paused, metrics)
    return ActionDecisions(transactions, parts, judging=judging), (
        executor,
        ActionSweeps(transactions, parts, judging=judging),
        ActionInvariants(transactions, metrics),
    )


def native_proxy(services: CoreServices, settings: AgentSettings) -> NativeProxy:
    """The shipped clients' model proxy over the standard model (step 14)."""
    return NativeProxy(
        (services.transactions, services.ports, services.ai, services.rate_limiter),
        settings.standard_route,
        ProxyMetrics(services.registry),
    )


def skill_store(
    services: CoreServices, clients: tuple[httpx.AsyncClient, httpx.AsyncClient]
) -> SkillStore:
    """The skills store over the process's GitHub and skills.sh clients (step 15)."""
    metrics = SkillMetrics(services.registry)
    sources = (
        GitHubSkills(clients[0], services.cache, metrics),
        SkillsDirectory(clients[1], services.cache, metrics),
        services.rate_limiter,
    )
    return SkillStore(services.transactions, sources)


def own_tools(
    services: CoreServices, settings: AgentSettings, pages: ResultPages
) -> tuple[AgentTool, ...]:
    """Leo's own toolsets: core, web, and the operator's platform (AG-D5)."""
    ratings = PlatformRatings(services.transactions)
    reads = PlatformReads((services.ai_spend, ratings, services.ports))
    return (
        *core_tools(pages),
        *web_tools(services.ai, settings.standard_route),
        *platform_tools(reads),
    )


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
    skill_clients = (github_client(settings.github_token()), directory_client())
    metrics, tracer = (
        RunMetrics(services.registry),
        services.tracer_provider.get_tracer(TRACER_NAME),
    )
    telemetry, pages = RunTelemetry(metrics, tracer), ResultPages(transactions, ports)
    cards = ActionCards(services.agent_tools, ports)
    tools = ToolParts(
        pages, RunSources(transactions, ports), tool_bulkhead(services.role),
        ToolMetrics(services.registry), tracer, card_proposer(services, cards),
    )  # fmt: skip
    routing, frames = TurnRouting(ToolRegistry(services.agent_tools), ports), TurnSaver(valkey)
    engine = RunEngine(
        EngineParts(
            transactions, services.ai, settings.standard_route(), run_log, leases, fleet,
            registry, services.outbox, turn_graph(frames), frames, ContextBuilder(ports),
            routing, tools, telemetry,
            AttachmentReader(transactions, (services.objects, DocumentReader(), pages)),
        )
    )  # fmt: skip
    starter = TurnStarter(
        TurnParts(
            transactions, ports, services.effects, services.rate_limiter, services.tasks,
            run_log, leases, fleet, threads, frames,
        )
    )  # fmt: skip
    streams = RunStreams(transactions, (run_log, tail), leases, metrics)
    lost_runs = LostRuns(transactions, (run_log, leases, fleet), metrics)
    care = ThreadCare(transactions, (services.ai, settings.utility_route()), ports)
    decisions, actions = action_gateway(services, cards, (run_log, frames), pages)
    feedback = Feedback((transactions, ports, threads), FeedbackMetrics(services.registry))
    person, operator = person_mount(ports), operator_mount(ports)
    try:
        yield FeatureParts(
            http_routers=(
                build_settings_router(preferences, ports),
                build_threads_router((threads, History(transactions, threads, cards)), person),
                build_turns_router((starter, streams), person),
                build_threads_router((threads, History(transactions, threads, cards)), operator),
                build_turns_router((starter, streams), operator),
                build_actions_router((decisions, ActionInbox(transactions, cards)), ports),
                build_feedback_router(feedback, ports),
                build_native_proxy_router(native_proxy(services, settings), ports),
                build_skills_router(skill_store(services, skill_clients), ports),
            ),
            task_handlers=task_handlers(
                Handlers(departures, lost_runs, engine, care, actions, CasePurge(transactions))
            ),
            subscriptions=subscriptions(departures, AfterTurn(services.tasks)),
            periodic_jobs=PERIODIC_JOBS,
            agent_tools=own_tools(services, settings, pages),
            queue_companions=(QueueCompanion(TaskQueue.AGENT, lambda: present_in_fleet(fleet)),),
            provides=(
                ACCOUNT_DATA_HANDLERS.bind(AgentAccountData(transactions, valkey)),
                ACTION_PROPOSALS.bind(
                    PortProposals(transactions, (services.agent_tools, cards, threads))
                ),
                ME_CONTRIBUTIONS.bind(preferences),
                SKILL_READER.bind(InstalledSkills()),
            ),
        )
    finally:
        await tail.close()
        await registry.close()
        await asyncio.gather(*(client.aclose() for client in skill_clients))


AGENT = FeatureModule(
    name="agent",
    build=build,
    models=(*THREAD_MODELS, *RUN_MODELS, *PERSON_MODELS),
    events=(TurnCompleted,),
    settings=(AgentSettings,),
    production_checks=(agent_model_set,),
    agent_tools=(*CORE_TOOLS, *WEB_TOOLS, *PLATFORM_TOOLS),
    objectives=AGENT_OBJECTIVES,
    monitors=AGENT_MONITORS,
    tracked=AGENT_TRACKED,
    account_data=(ACCOUNT_DATA,),
)
