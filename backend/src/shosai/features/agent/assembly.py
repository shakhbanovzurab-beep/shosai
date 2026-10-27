"""The agent slice's parts as `module.build` assembles them: the tool bulkhead, the Action
Gateway, voice, the shipped clients' proxy, the skills store, the operator's pictures and Leo's
own toolsets, each over the process's core services."""

import asyncio
from typing import Final

import httpx

from shosai.core.agent_tools.bindings import AgentTool
from shosai.core.config.roles import ProcessRole
from shosai.core.db.engines import DATABASE_PROFILES
from shosai.core.features import CoreServices
from shosai.features.agent.application.action_cards import ActionCards
from shosai.features.agent.application.action_decisions import ActionDecisions
from shosai.features.agent.application.action_execution import ActionExecution
from shosai.features.agent.application.action_invariants import ActionInvariants
from shosai.features.agent.application.action_proposal import ActionProposer
from shosai.features.agent.application.action_sweeps import ActionSweeps
from shosai.features.agent.application.egress_calls import EgressCalls
from shosai.features.agent.application.friction_judging import FrictionJudging
from shosai.features.agent.application.native_proxy import NativeProxy
from shosai.features.agent.application.paused_runs import PausedRuns
from shosai.features.agent.application.platform_images import PlatformImages
from shosai.features.agent.application.platform_ratings import PlatformRatings
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.application.skill_store import SkillStore
from shosai.features.agent.application.threads import Threads
from shosai.features.agent.application.tool_offer import TurnRouting
from shosai.features.agent.application.tool_round import ToolParts
from shosai.features.agent.application.voice_approval import VoiceApproval
from shosai.features.agent.application.voice_turns import AgentVoiceTurns, VoiceParts
from shosai.features.agent.channels.agent_tools import core_tools
from shosai.features.agent.channels.platform_reads import PlatformReads
from shosai.features.agent.channels.platform_tools import platform_tools
from shosai.features.agent.channels.web_tools import web_tools
from shosai.features.agent.infrastructure.action_metrics import ActionMetrics
from shosai.features.agent.infrastructure.github_skills import GitHubSkills
from shosai.features.agent.infrastructure.proxy_metrics import ProxyMetrics
from shosai.features.agent.infrastructure.run_log import RunLog
from shosai.features.agent.infrastructure.skill_metrics import SkillMetrics
from shosai.features.agent.infrastructure.skills_directory import SkillsDirectory
from shosai.features.agent.infrastructure.turn_saver import TurnSaver
from shosai.features.agent.settings import AgentSettings

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


def voice_turns(
    services: CoreServices,
    parts: tuple[Threads, TurnRouting, ToolParts, ActionCards, ActionDecisions],
) -> AgentVoiceTurns:
    """Leo's voice conversations on the threads, the routing and the tools of text turns, with
    cards read back and approved by voice through the gateway."""
    threads, routing, tools, cards, decisions = parts
    transactions, ports = services.transactions, services.ports
    approval = VoiceApproval(transactions, ports, cards, decisions)
    return AgentVoiceTurns(
        VoiceParts(transactions, ports, threads, routing, tools, services.outbox, approval)
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


def platform_images(services: CoreServices, settings: AgentSettings) -> PlatformImages:
    """The operator's pictures over the provider port and the homes' buckets (step 16b2)."""
    return PlatformImages(
        services.transactions, services.objects, (services.ai, settings.image_route)
    )


def own_tools(
    services: CoreServices, pages: ResultPages, drawing: tuple[AgentSettings, PlatformImages]
) -> tuple[AgentTool, ...]:
    """Leo's own toolsets: core, web, and the operator's platform with its pictures (AG-D5)."""
    settings, images = drawing
    ratings = PlatformRatings(services.transactions)
    reads = PlatformReads((services.ai_spend, ratings, services.ports))
    return (
        *core_tools(pages),
        *web_tools(services.ai, settings.standard_route),
        *platform_tools(reads, images),
    )
