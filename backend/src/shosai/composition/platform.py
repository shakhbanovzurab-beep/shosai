"""The platform of one process: its clients, its task system and the slices built on them.

Steps, in order, each named when it fails (§3.11):

1. `features` — no slice is listed twice;
2. `databases` — one engine per home, the check of each home's identity and schema: another
   home's database or a schema behind the code stops the start, a home out of reach does
   not (F1-D8);
3. `shared_services` — Valkey, the cache and the bucket; none is contacted here, so an
   outage of one never stops the start (§13.2);
4. `tasks` — the brokers, the sender and the outbox of the listed event classes;
   `ai` — the AI provider port and the exchange rates, with their HTTP clients;
5. `feature:<name>` — each slice built from the core services, in the listed order;
6. `events` — the catalog with every subscription, and every task registered;
7. `schedule` — core's and every slice's periodic jobs and due-row sources, each named once
   and each with its task registered;
8. `probes` — the readiness probes of core and of every slice, each name once.

Everything opened is closed in reverse order when the block ends: slices first, then the
clients, then the engines.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

import structlog
from redis.asyncio import Redis

from shosai.composition.agent_tools import install_agent_tools
from shosai.composition.ai import AiDependencies, PlatformAi, open_ai
from shosai.composition.email import PlatformEmail, open_email
from shosai.composition.features import check_features, platform_events
from shosai.composition.schedule import scheduled_jobs
from shosai.composition.startup import start_step
from shosai.composition.telemetry import ProcessTelemetry
from shosai.core.agent_tools.catalog import AgentToolCatalog
from shosai.core.cache.metrics import CacheMetrics
from shosai.core.cache.redis_cache import RedisCache
from shosai.core.config.loading import Settings
from shosai.core.config.roles import ProcessRole
from shosai.core.db.engines import HomeDatabases
from shosai.core.db.home_checks import HomeGate, HomeState
from shosai.core.db.metrics import DatabaseMetrics, register_pool_occupancy
from shosai.core.db.migrations import MigrationHistory
from shosai.core.db.partitions.system import partition_task_handlers
from shosai.core.db.partitions.upkeep import PartitionMetrics
from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.system import email_task_handlers
from shosai.core.events.catalog import EventCatalog, EventTypes
from shosai.core.events.metrics import EventMetrics
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.resources import EventResources
from shosai.core.events.system import event_task_handlers
from shosai.core.features import CoreServices, FeatureModule, FeatureParts, combine_parts
from shosai.core.health.dependencies import home_probe, redis_probe, storage_probe
from shosai.core.health.probes import DependencyProbe
from shosai.core.idempotency.batch import EffectBatch
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.idempotency.metrics import EffectKeyMetrics
from shosai.core.idempotency.system import effect_key_task_handlers
from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import connect_redis
from shosai.core.kv.locks import DistributedLocks
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.storage.metrics import StorageMetrics
from shosai.core.storage.s3_client import S3Calls, open_s3_client
from shosai.core.storage.s3_multipart import S3MultipartUploads
from shosai.core.storage.s3_objects import S3ObjectStorage
from shosai.core.tasks.system import TaskSystem, build_task_system

log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Platform:
    """What a role runs on: the core services, the tasks, the events and the slices' parts."""

    services: CoreServices
    tasks: TaskSystem
    events: EventResources
    parts: FeatureParts
    probes: tuple[DependencyProbe, ...]
    jobs: tuple[PeriodicJob, ...]


@dataclass(frozen=True, slots=True)
class _Process:
    settings: Settings
    role: ProcessRole
    telemetry: ProcessTelemetry


@dataclass(frozen=True, slots=True)
class _Homes:
    databases: HomeDatabases
    gate: HomeGate
    transactions: HomeTransactions


@dataclass(frozen=True, slots=True)
class _Writers:
    tasks: TaskSystem
    outbox: EventOutbox
    effects: EffectLedger
    ai: PlatformAi
    email: PlatformEmail


@dataclass(frozen=True, slots=True)
class _Clients:
    valkey: Redis
    cache: Redis
    objects: S3ObjectStorage
    uploads: S3MultipartUploads


@asynccontextmanager
async def open_platform(
    settings: Settings,
    role: ProcessRole,
    telemetry: ProcessTelemetry,
    features: Sequence[FeatureModule],
) -> AsyncIterator[Platform]:
    """Open everything a role needs, step by step; close it in reverse order after the block."""
    process = _Process(settings, role, telemetry)
    with start_step("features"):
        check_features(features)
    async with AsyncExitStack() as stack:
        with start_step("databases"):
            homes = await _open_homes(process, stack)
        with start_step("shared_services"):
            clients = await _open_clients(process, stack)
        with start_step("tasks"):
            tasks = build_task_system(clients.valkey, telemetry.registry, telemetry.tracer_provider)
            outbox = EventOutbox(EventTypes(platform_events(features)))
            effect_keys = EffectKeyMetrics(telemetry.registry)
            effects = EffectLedger(effect_keys)
        with start_step("ai"):
            dependencies = AiDependencies(
                homes.transactions,
                tasks.sender,
                effects,
                EffectBatch(effect_keys),
                clients.valkey,
                outbox,
                telemetry.registry,
            )
            ai = await open_ai(settings, dependencies, stack)
        with start_step("email"):
            email = open_email(settings, homes.transactions, telemetry.registry)
        writers = _Writers(tasks, outbox, effects, ai, email)
        services = _core_services(process, homes, clients, writers)
        built: list[FeatureParts] = []
        for feature in features:
            with start_step(f"feature:{feature.name}"):
                built.append(await stack.enter_async_context(feature.build(services)))
        # Маршруты ссылок из писем — ядра, но api обслуживает их вместе с маршрутами срезов.
        parts = combine_parts(
            [FeatureParts(http_routers=(email.router(services.rate_limiter),)), *built]
        )
        with start_step("events"):
            events = EventResources(
                catalog=EventCatalog(platform_events(features), parts.subscriptions),
                transactions=homes.transactions,
                metrics=EventMetrics(telemetry.registry),
                tracer_provider=telemetry.tracer_provider,
            )
            tasks.register(
                [
                    *event_task_handlers(events, tasks.sender),
                    *effect_key_task_handlers(homes.transactions, effect_keys),
                    *partition_task_handlers(
                        homes.transactions, PartitionMetrics(telemetry.registry)
                    ),
                    *writers.ai.task_handlers(),
                    *email_task_handlers(email.delivery, tasks.sender),
                    *parts.task_handlers,
                ]
            )
            writers.ai.settlements.install(parts.cost_settlements)
            email.install(parts.email_templates)
            install_agent_tools(features, built, services.agent_tools)
        with start_step("schedule"):
            jobs = scheduled_jobs(parts, tasks)
        with start_step("probes"):
            probes = (*_core_probes(homes, clients), *parts.probes)
            check_probe_names(probes)
        yield Platform(services, tasks, events, parts, probes, jobs)


def check_probe_names(probes: Sequence[DependencyProbe]) -> None:
    """Refuse two probes with one name: the readiness report could not tell them apart."""
    names = [probe.name for probe in probes]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        message = f"пробы готовности названы дважды: {', '.join(duplicates)}"
        raise ValueError(message)


async def _open_homes(process: _Process, stack: AsyncExitStack) -> _Homes:
    telemetry = process.telemetry
    databases = HomeDatabases.create(
        {home: process.settings.homes[home].database_url for home in Home},
        process.role,
        tracer_provider=telemetry.tracer_provider,
    )
    stack.push_async_callback(databases.dispose)
    register_pool_occupancy(telemetry.registry, databases)
    metrics = DatabaseMetrics(telemetry.registry)
    gate = HomeGate(databases, MigrationHistory.load(), metrics)
    for check in await gate.verify_at_start():
        if check.state is HomeState.VERIFIED:
            log.info("База дома проверена", home=check.home.value, revision=check.revision)
    return _Homes(databases, gate, HomeTransactions(databases, gate, metrics))


async def _open_clients(process: _Process, stack: AsyncExitStack) -> _Clients:
    settings, telemetry = process.settings, process.telemetry
    tracer = telemetry.tracer_provider
    # Имя клиента показывает роль процесса в CLIENT LIST сервера.
    client_name = f"shosai-{process.role.value}"
    valkey = connect_redis(settings.shared_services.valkey_url, client_name, tracer)
    stack.push_async_callback(valkey.aclose)
    cache = connect_redis(settings.shared_services.redis_cache_url, client_name, tracer)
    stack.push_async_callback(cache.aclose)
    s3 = await stack.enter_async_context(open_s3_client(settings.storage))
    calls = S3Calls(settings.storage.s3_bucket, StorageMetrics(telemetry.registry), tracer)
    return _Clients(
        valkey=valkey,
        cache=cache,
        objects=S3ObjectStorage(s3, calls),
        uploads=S3MultipartUploads(s3, calls),
    )


def _core_services(
    process: _Process, homes: _Homes, clients: _Clients, writers: _Writers
) -> CoreServices:
    telemetry = process.telemetry
    kv_metrics = KeyValueMetrics(telemetry.registry)
    return CoreServices(
        settings=process.settings,
        role=process.role,
        transactions=homes.transactions,
        tasks=writers.tasks.sender,
        outbox=writers.outbox,
        effects=writers.effects,
        ai=writers.ai.providers,
        ai_spend=writers.ai.operator,
        email=writers.email.port,
        agent_tools=AgentToolCatalog(),
        exchange_rates=writers.ai.rates,
        cache=RedisCache(clients.cache, CacheMetrics(telemetry.registry)),
        objects=clients.objects,
        uploads=clients.uploads,
        locks=DistributedLocks(clients.valkey, kv_metrics),
        rate_limiter=RateLimiter(clients.valkey, kv_metrics),
        valkey=clients.valkey,
        registry=telemetry.registry,
        tracer_provider=telemetry.tracer_provider,
    )


def _core_probes(homes: _Homes, clients: _Clients) -> tuple[DependencyProbe, ...]:
    return (
        *(home_probe(home, homes.databases, homes.gate) for home in Home),
        redis_probe("valkey", clients.valkey),
        redis_probe("cache", clients.cache),
        storage_probe(clients.objects),
    )
