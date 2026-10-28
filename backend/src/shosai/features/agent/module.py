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

from opentelemetry.trace import Tracer

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.documents.extraction import DocumentReader
from shosai.core.features import CoreServices, FeatureModule, FeatureParts, QueueCompanion
from shosai.core.ports.directory import PortDirectory
from shosai.core.tasks.queues import TaskQueue
from shosai.features.agent.application.account_data import ACCOUNT_DATA, AgentAccountData
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_inbox import ActionInbox
from shosai.features.agent.application.after_turn import AfterTurn
from shosai.features.agent.application.case_care import CasePurge
from shosai.features.agent.application.departures import Departures
from shosai.features.agent.application.feedback import Feedback
from shosai.features.agent.application.fleet_presence import present_in_fleet
from shosai.features.agent.application.history import History
from shosai.features.agent.application.installed_skills import InstalledSkills
from shosai.features.agent.application.lost_runs import LostRuns
from shosai.features.agent.application.memory_context import MemoryContext
from shosai.features.agent.application.person_words import AgentPersonWords
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
from shosai.features.agent.application.thread_care import ThreadCare
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.tool_offer import TurnRouting
from shosai.features.agent.application.tool_registry import ToolRegistry
from shosai.features.agent.application.tool_round import ToolParts
from shosai.features.agent.application.turn_commit import TurnParts
from shosai.features.agent.application.turn_start import TurnStarter
from shosai.features.agent.assembly import (
    action_gateway,
    card_proposer,
    native_proxy,
    own_tools,
    platform_images,
    skill_store,
    tool_bulkhead,
    voice_turns,
)
from shosai.features.agent.channels.agent_tools import CORE_TOOLS
from shosai.features.agent.channels.http.actions import build_actions_router
from shosai.features.agent.channels.http.callers import operator_mount, person_mount
from shosai.features.agent.channels.http.feedback import build_feedback_router
from shosai.features.agent.channels.http.images import build_images_router
from shosai.features.agent.channels.http.native_proxy import build_native_proxy_router
from shosai.features.agent.channels.http.settings import build_settings_router
from shosai.features.agent.channels.http.skills import build_skills_router
from shosai.features.agent.channels.http.threads import build_threads_router
from shosai.features.agent.channels.http.turns import build_turns_router
from shosai.features.agent.channels.image_specs import IMAGE_TOOLS
from shosai.features.agent.channels.platform_specs import PLATFORM_TOOLS
from shosai.features.agent.channels.subscriptions import subscriptions
from shosai.features.agent.channels.tasks import PERIODIC_JOBS, Handlers, task_handlers
from shosai.features.agent.channels.web_tools import WEB_TOOLS
from shosai.features.agent.contracts import ACTION_PROPOSALS, SKILL_READER
from shosai.features.agent.contracts.events import SkillRemoved, TurnCompleted
from shosai.features.agent.contracts.memory import PERSON_WORDS
from shosai.features.agent.contracts.voice import VOICE_TURNS
from shosai.features.agent.infrastructure.feedback_metrics import FeedbackMetrics
from shosai.features.agent.infrastructure.fleet import Fleet
from shosai.features.agent.infrastructure.github_skills import github_client
from shosai.features.agent.infrastructure.image_records import IMAGE_MODELS
from shosai.features.agent.infrastructure.log_tail import LogTail
from shosai.features.agent.infrastructure.person_records import PERSON_MODELS
from shosai.features.agent.infrastructure.profile_key import profile_boundary_key
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.run_metrics import RunMetrics
from shosai.features.agent.infrastructure.run_records import RUN_MODELS
from shosai.features.agent.infrastructure.skills_directory import directory_client
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


def tool_parts(
    services: CoreServices, tracer: Tracer
) -> tuple[ToolParts, ResultPages, ActionCards]:
    """A run's tools: stored results, sources, the bulkhead, their metrics and the cards."""
    ports = services.ports
    pages = ResultPages(services.transactions, ports)
    cards = ActionCards(services.agent_tools, ports)
    tools = ToolParts(
        pages, RunSources(services.transactions, ports), tool_bulkhead(services.role),
        ToolMetrics(services.registry), tracer, card_proposer(services, cards),
    )  # fmt: skip
    return tools, pages, cards


def context_builder(services: CoreServices, ports: PortDirectory) -> ContextBuilder:
    """The turn's context, its profile core's boundary keyed to the platform's key."""
    memory = MemoryContext(ports, profile_boundary_key(services.settings.crypto))
    return ContextBuilder(ports, memory=memory)


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Settings > Leo, threads and their history, turns and runs, departures, and the
    handler of a person's data."""
    transactions, ports, valkey = services.transactions, services.ports, services.valkey
    preferences, departures = AgentPreferences(transactions), Departures(transactions, ports)
    threads = Threads(transactions, (ports, services.effects))
    run_log, leases, fleet = RunLog(valkey), ThreadLeases(valkey), Fleet(valkey)
    tail, registry = LogTail(valkey, run_log), RunRegistry(leases, fleet)
    settings = services.settings.features.get(AgentSettings)
    skill_clients = (github_client(settings.github_token()), directory_client())
    tracer = services.tracer_provider.get_tracer(TRACER_NAME)
    metrics = RunMetrics(services.registry)
    tools, pages, cards = tool_parts(services, tracer)
    routing, frames = TurnRouting(ToolRegistry(services.agent_tools), ports), TurnSaver(valkey)
    engine = RunEngine(
        EngineParts(
            transactions, services.ai, settings.standard_route(), run_log, leases, fleet,
            registry, services.outbox, turn_graph(frames), frames, context_builder(services, ports),
            routing, tools, RunTelemetry(metrics, tracer),
            AttachmentReader(transactions, (services.objects, DocumentReader(), pages)),
            ports=ports,
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
    voice = voice_turns(services, (threads, routing, tools, cards, decisions))
    images = platform_images(services, settings)
    upkeep = Handlers(
        departures, lost_runs, engine, care, actions, (CasePurge(transactions), images)
    )
    proposals = PortProposals(transactions, (services.agent_tools, cards, threads))
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
                build_images_router(images, operator),
            ),
            task_handlers=task_handlers(upkeep),
            subscriptions=subscriptions(departures, AfterTurn(services.tasks)),
            periodic_jobs=PERIODIC_JOBS,
            agent_tools=own_tools(services, pages, (settings, images)),
            queue_companions=(QueueCompanion(TaskQueue.AGENT, lambda: present_in_fleet(fleet)),),
            provides=(
                ACCOUNT_DATA_HANDLERS.bind(AgentAccountData(transactions, valkey)),
                ACTION_PROPOSALS.bind(proposals),
                ME_CONTRIBUTIONS.bind(preferences),
                SKILL_READER.bind(InstalledSkills()),
                PERSON_WORDS.bind(AgentPersonWords()),
                VOICE_TURNS.bind(voice),
            ),
        )
    finally:
        await tail.close()
        await registry.close()
        await asyncio.gather(*(client.aclose() for client in skill_clients))


AGENT = FeatureModule(
    name="agent",
    build=build,
    models=(*THREAD_MODELS, *RUN_MODELS, *PERSON_MODELS, *IMAGE_MODELS),
    events=(TurnCompleted, SkillRemoved),
    settings=(AgentSettings,),
    production_checks=(agent_model_set,),
    agent_tools=(*CORE_TOOLS, *WEB_TOOLS, *PLATFORM_TOOLS, *IMAGE_TOOLS),
    objectives=AGENT_OBJECTIVES,
    monitors=AGENT_MONITORS,
    tracked=AGENT_TRACKED,
    account_data=(ACCOUNT_DATA,),
)
