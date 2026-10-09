"""Alembic for both homes: one linear history applied home by home (ADR 0010, §17).

Migrations run under the migration role over a direct connection — PgBouncer is only for
the application. A session advisory lock keeps two runs of the same home from
interleaving, and `lock_timeout` stops a DDL statement that would queue every query of
a busy table behind it. The RU home goes first; the first failure stops the run.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Self

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from sqlalchemy import Connection, MetaData, NullPool, make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from shosai.core.db.engines import CONNECT_TIMEOUT_SECONDS, DRIVER
from shosai.core.kernel.homes import Home

SCRIPT_LOCATION: Final = "shosai:migrations"
TARGET_ATTRIBUTE: Final = "shosai.target"
METADATA_ATTRIBUTE: Final = "shosai.metadata"
CONNECTION_ATTRIBUTE: Final = "connection"
# «WhisperM»: один ключ у всех запусков миграций одного дома.
MIGRATION_LOCK_KEY: Final = 0x5768_6973_7065_724D
LOCK_TIMEOUT: Final = "5s"
APPLICATION_NAME: Final = "shosai-migrate"

type AlembicCommand = Callable[[Config, str], None]


@dataclass(frozen=True, slots=True)
class MigrationTarget:
    """One home's database as the migration role sees it, and the role of the application."""

    home: Home
    url: SecretStr
    application_role: str


class RevisionState(StrEnum):
    """Where a database's revision stands against the history this code carries."""

    AT_HEAD = "at_head"
    # Ревизия неизвестна этой истории — значит, её применил более новый релиз: миграции
    # только расширяют схему (§17), и откат образа обязан стартовать (решение F1-D7).
    NEWER = "newer"
    BEHIND = "behind"


@dataclass(frozen=True, slots=True)
class MigrationHistory:
    """The head of the code's history and every revision it knows."""

    head: str
    revisions: frozenset[str]

    @classmethod
    def load(cls) -> Self:
        """Read the history from the scripts shipped in the package."""
        script = ScriptDirectory.from_config(alembic_config())
        head = script.get_current_head()
        if head is None:
            message = "в истории миграций нет ревизий"
            raise RuntimeError(message)
        return cls(head, frozenset(rev.revision for rev in script.walk_revisions()))

    def state_of(self, revision: str | None) -> RevisionState:
        """At the head, newer than this code, or behind it (including no revision at all)."""
        if revision == self.head:
            return RevisionState.AT_HEAD
        if revision is not None and revision not in self.revisions:
            return RevisionState.NEWER
        return RevisionState.BEHIND


def alembic_config() -> Config:
    """The configuration of the runner: the scripts are package data of `shosai`."""
    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    return config


async def upgrade(
    targets: Sequence[MigrationTarget], metadata: MetaData, revision: str = "head"
) -> None:
    """Upgrade each home in turn; the first failure stops the run."""
    for target in targets:
        await _run(target, metadata, command.upgrade, revision)


async def downgrade(targets: Sequence[MigrationTarget], metadata: MetaData, revision: str) -> None:
    """Downgrade each home in turn, in the order given."""
    for target in targets:
        await _run(target, metadata, command.downgrade, revision)


async def current_revision(target: MigrationTarget) -> str | None:
    """The revision a home's database is stamped with, or None before the first migration."""
    engine = _migration_engine(target)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_read_revision)
    finally:
        await engine.dispose()


async def _run(
    target: MigrationTarget, metadata: MetaData, alembic_command: AlembicCommand, revision: str
) -> None:
    engine = _migration_engine(target)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_locked, target, metadata, alembic_command, revision)
    finally:
        await engine.dispose()


def _locked(
    connection: Connection,
    target: MigrationTarget,
    metadata: MetaData,
    alembic_command: AlembicCommand,
    revision: str,
) -> None:
    # Блокировка сессионная: соединение прямое, мимо PgBouncer, и живёт весь запуск.
    connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
    connection.execute(
        text("SELECT set_config('lock_timeout', :value, false)"), {"value": LOCK_TIMEOUT}
    )
    connection.commit()
    try:
        config = alembic_config()
        config.attributes[CONNECTION_ATTRIBUTE] = connection
        config.attributes[TARGET_ATTRIBUTE] = target
        config.attributes[METADATA_ATTRIBUTE] = metadata
        alembic_command(config, revision)
    finally:
        connection.rollback()
        connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
        connection.commit()


def _read_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def _migration_engine(target: MigrationTarget) -> AsyncEngine:
    return create_async_engine(
        make_url(target.url.get_secret_value()).set(drivername=DRIVER),
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={
            "prepare_threshold": None,
            "connect_timeout": CONNECT_TIMEOUT_SECONDS,
            "application_name": APPLICATION_NAME,
        },
    )
