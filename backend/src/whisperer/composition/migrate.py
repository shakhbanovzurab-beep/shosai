"""`whisperer migrate`: one-shot Alembic commands for both homes (ADR 0010, §17).

`upgrade` applies the history to the RU home, then the EU home, and stops at the first
failure; `current` only reads. Both log each home's revision. The command connects as
the migration role, directly: only it receives `HOME_<H>_MIGRATION_DATABASE_URL`, the
long-running roles never do. There is no downgrade command: migrations only expand the
schema, and a release is rolled back by starting the previous image (§13.3, F1-D7).
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Final
from urllib.parse import unquote, urlsplit

import structlog

from whisperer.composition.features import FEATURES, feature_checks
from whisperer.composition.metadata import application_metadata
from whisperer.composition.startup import load_process_settings
from whisperer.core.config.loading import Settings
from whisperer.core.config.roles import ProcessRole
from whisperer.core.config.sections import home_prefix
from whisperer.core.db.migrations import MigrationTarget, current_revision, upgrade
from whisperer.core.kernel.homes import Home
from whisperer.core.observability.logs import configure_logging
from whisperer.core.observability.metrics import ObservabilityMetrics, build_metrics_registry

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
log = structlog.stdlib.get_logger(__name__)


class MigrateAction(StrEnum):
    """What `whisperer migrate` does."""

    UPGRADE = "upgrade"
    CURRENT = "current"


class MigrationAddressError(Exception):
    """A home lacks the migration address or the application role in its address."""


def migration_targets(settings: Settings) -> list[MigrationTarget]:
    """Each home's migration address and application role, RU first."""
    targets: list[MigrationTarget] = []
    problems: list[str] = []
    for home in Home:
        prefix = home_prefix(home)
        home_settings = settings.homes[home]
        role = urlsplit(home_settings.database_url.get_secret_value()).username
        if home_settings.migration_database_url is None:
            problems.append(f"{prefix}MIGRATION_DATABASE_URL: нужна команде migrate")
        if not role:
            problems.append(f"{prefix}DATABASE_URL: в адресе нет роли приложения")
        if home_settings.migration_database_url is not None and role:
            targets.append(
                MigrationTarget(home, home_settings.migration_database_url, unquote(role))
            )
    if problems:
        raise MigrationAddressError("\n".join(problems))
    return targets


async def run_migrate(environ: Mapping[str, str], action: MigrateAction) -> int:
    """Run the command for both homes; return the exit code."""
    role = ProcessRole.MIGRATE
    settings = load_process_settings(environ, role, feature_checks(FEATURES))
    if settings is None:
        return EXIT_FAILED
    metrics = ObservabilityMetrics(build_metrics_registry())
    pipeline = configure_logging(settings.observability, role, metrics)
    try:
        return await _migrate(settings, action)
    finally:
        pipeline.close()


async def _migrate(settings: Settings, action: MigrateAction) -> int:
    try:
        targets = migration_targets(settings)
        if action is MigrateAction.UPGRADE:
            log.info("Миграция домов начата", homes=[target.home.value for target in targets])
            await upgrade(targets, application_metadata())
        for target in targets:
            revision = await current_revision(target)
            log.info("Ревизия базы дома", home=target.home.value, revision=revision)
    except MigrationAddressError as error:
        log.critical("Миграция не начата", reason=str(error))
        return EXIT_FAILED
    # Любой сбой Alembic или базы останавливает команду; строка — со стеком.
    except Exception:
        log.exception("Миграция завершилась ошибкой", action=action.value)
        return EXIT_FAILED
    return EXIT_OK
