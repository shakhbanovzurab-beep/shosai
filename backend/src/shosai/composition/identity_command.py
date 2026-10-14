"""`shosai identity grant-operator --email ADDRESS --role ROLE`: the first owner (SM-12).

The platform starts with no operator, and only an owner gives roles over the API; this
command gives the first one. It opens both homes over the application role, checks them as
a process start does, finds the active account of the address through the directory and
adds the role in the account's home, with the audit event the relay later delivers.
"""

from collections.abc import Mapping
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Final

import structlog

from shosai.composition.features import FEATURES, platform_events
from shosai.composition.startup import load_process_settings
from shosai.core.cache.metrics import CacheMetrics
from shosai.core.cache.redis_cache import RedisCache
from shosai.core.config.loading import Settings
from shosai.core.config.roles import ProcessRole
from shosai.core.db.engines import HomeDatabases
from shosai.core.db.home_checks import HomeGate, HomeState
from shosai.core.db.metrics import DatabaseMetrics
from shosai.core.db.migrations import MigrationHistory
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kernel.errors import AppError
from shosai.core.kernel.homes import Home
from shosai.core.kv.connection import connect_redis
from shosai.core.kv.locks import DistributedLocks
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.observability.logs import configure_logging
from shosai.core.observability.metrics import ObservabilityMetrics, build_metrics_registry
from shosai.features.identity.application.operators import Operators
from shosai.features.identity.contracts import OperatorRole
from shosai.features.identity.domain.directory import email_hmac
from shosai.features.identity.domain.emails import InvalidEmailError, normalize_email
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.settings import IdentitySettings

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GrantOperatorCommand:
    """Whose account gets which role."""

    email: str
    role: OperatorRole


async def run_grant_operator(environ: Mapping[str, str], command: GrantOperatorCommand) -> int:
    """Give the role; return the exit code."""
    role = ProcessRole.IDENTITY
    settings = load_process_settings(environ, role, FEATURES)
    if settings is None:
        return EXIT_FAILED
    pipeline = configure_logging(
        settings.observability, role, ObservabilityMetrics(build_metrics_registry())
    )
    try:
        async with AsyncExitStack() as stack:
            return await _granted(settings, command, stack)
    finally:
        pipeline.close()


async def _granted(settings: Settings, command: GrantOperatorCommand, stack: AsyncExitStack) -> int:
    try:
        address = normalize_email(command.email)
    except InvalidEmailError:
        log.error("Роль не выдана: адрес не похож на адрес почты")
        return EXIT_FAILED
    operators = await _operators(settings, stack)
    if operators is None:
        return EXIT_FAILED
    key = settings.features.get(IdentitySettings).identity_directory_hmac_key
    try:
        view = await operators.grant(
            email_hmac(key.get_secret_value().encode(), address), command.role
        )
    except AppError as refused:
        log.error("Роль не выдана", code=refused.code)
        return EXIT_FAILED
    log.info("Роль оператора выдана", user_id=str(view.user_id), roles=sorted(view.roles))
    return EXIT_OK


async def _operators(settings: Settings, stack: AsyncExitStack) -> Operators | None:
    registry = build_metrics_registry()
    databases = HomeDatabases.create(
        {home: settings.homes[home].database_url for home in Home}, ProcessRole.IDENTITY
    )
    stack.push_async_callback(databases.dispose)
    metrics = DatabaseMetrics(registry)
    gate = HomeGate(databases, MigrationHistory.load(), metrics)
    checks = await gate.verify_at_start()
    out_of_reach = [check.home.value for check in checks if check.state is not HomeState.VERIFIED]
    if out_of_reach:
        log.error("Роль не выдана: дом недоступен", homes=out_of_reach)
        return None
    shared = settings.shared_services
    valkey = connect_redis(shared.valkey_url, "shosai-identity-cli")
    stack.push_async_callback(valkey.aclose)
    cache = connect_redis(shared.redis_cache_url, "shosai-identity-cli-cache")
    stack.push_async_callback(cache.aclose)
    transactions = HomeTransactions(databases, gate, metrics)
    return Operators(
        transactions,
        Directory(transactions, RedisCache(cache, CacheMetrics(registry))),
        EventOutbox(EventTypes(platform_events(FEATURES))),
        DistributedLocks(valkey, KeyValueMetrics(registry)),
    )
