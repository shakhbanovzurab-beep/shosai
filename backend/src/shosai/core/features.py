"""What a slice contributes to the backend: one `FeatureModule` per slice (target architecture §5).

Composition lists the modules explicitly (`composition/features.py`) and wires them into
every role; nothing is found by importing modules. A module declares statically what
must be known before any client exists — its tables, its event classes and its production
checks — and builds the rest from the core services when the process starts: HTTP and
WebSocket routers, task handlers, event subscriptions, scheduler loops and readiness probes.

`build` is an async context manager entered at start in every role and left at stop, so
a slice opens and closes its own clients with the process (draft lesson: feature start
hooks that nothing called). Every role builds every slice: each role registers every
task (§14 rule 9), and each part is used only by the role it belongs to.
"""

import re
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any, Final

from fastapi import APIRouter
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from shosai.core.cache.port import Cache
from shosai.core.config.gate import ProductionCheck
from shosai.core.config.loading import Settings
from shosai.core.config.roles import ProcessRole
from shosai.core.db.model_base import ModelBase
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.domain_event import DomainEvent
from shosai.core.events.outbox import EventOutbox
from shosai.core.events.subscriptions import EventSubscription
from shosai.core.health.probes import DependencyProbe
from shosai.core.idempotency.ledger import EffectLedger
from shosai.core.kv.locks import DistributedLocks
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.runtime.loops import ScheduledLoop
from shosai.core.storage.port import MultipartUploads, ObjectStorage
from shosai.core.tasks.declaration import TaskHandler
from shosai.core.tasks.sender import TaskSender

FEATURE_NAME: Final = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True, slots=True)
class CoreServices:
    """What core gives a slice: the process's clients, ports and telemetry, by injection."""

    settings: Settings
    role: ProcessRole
    transactions: HomeTransactions
    tasks: TaskSender
    outbox: EventOutbox
    effects: EffectLedger
    cache: Cache
    objects: ObjectStorage
    uploads: MultipartUploads
    locks: DistributedLocks
    rate_limiter: RateLimiter
    # Сам клиент Valkey — для собственных структур среза: очереди транскрипта, состояния встреч.
    valkey: Redis
    registry: CollectorRegistry
    tracer_provider: TracerProvider


@dataclass(frozen=True, slots=True)
class FeatureParts:
    """What a slice built for this process; each role takes the parts it serves."""

    http_routers: tuple[APIRouter, ...] = ()
    ws_routers: tuple[APIRouter, ...] = ()
    task_handlers: tuple[TaskHandler[Any], ...] = ()
    subscriptions: tuple[EventSubscription[Any], ...] = ()
    loops: tuple[ScheduledLoop, ...] = ()
    probes: tuple[DependencyProbe, ...] = ()


def combine_parts(parts: Sequence[FeatureParts]) -> FeatureParts:
    """The parts of every slice of the process, in the listed order."""
    return FeatureParts(
        http_routers=tuple(router for part in parts for router in part.http_routers),
        ws_routers=tuple(router for part in parts for router in part.ws_routers),
        task_handlers=tuple(handler for part in parts for handler in part.task_handlers),
        subscriptions=tuple(item for part in parts for item in part.subscriptions),
        loops=tuple(loop for part in parts for loop in part.loops),
        probes=tuple(probe for part in parts for probe in part.probes),
    )


type FeatureBuilder = Callable[[CoreServices], AbstractAsyncContextManager[FeatureParts]]


@asynccontextmanager
async def no_parts(_services: CoreServices) -> AsyncIterator[FeatureParts]:
    """The builder of a slice that only declares tables or events."""
    yield FeatureParts()


@dataclass(frozen=True, slots=True)
class FeatureModule:
    """One slice as composition sees it."""

    # Имя пакета среза в features/; уникально в бэкенде.
    name: str
    build: FeatureBuilder = no_parts
    models: tuple[type[ModelBase], ...] = ()
    events: tuple[type[DomainEvent], ...] = ()
    production_checks: tuple[ProductionCheck, ...] = ()

    def __post_init__(self) -> None:
        if not FEATURE_NAME.fullmatch(self.name):
            message = f"имя среза {self.name!r} — имя его пакета в snake_case"
            raise ValueError(message)
