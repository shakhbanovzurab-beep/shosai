"""Engines of one process: exactly one connection pool per data home (§4.1, §14 rule 2).

The application reaches each home's PostgreSQL through PgBouncer in transaction mode
(ADR 0001), so nothing may outlive a transaction on a server connection. psycopg runs
every statement unprepared (`prepare_threshold=None`): Parse, Bind and Execute leave in
one message, so a statement costs one round trip and no named statement is left on a
server connection that the next client reuses (ADR 0013).
"""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType
from typing import Final, Self

from opentelemetry.sdk.trace import TracerProvider
from pydantic import SecretStr
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shosai.core.config.roles import ProcessRole
from shosai.core.db.tracing import trace_statements
from shosai.core.kernel.homes import Home

DRIVER: Final = "postgresql+psycopg"
CONNECT_TIMEOUT_SECONDS: Final = 5
# Меньше idle-таймаута серверов и пулеров провайдеров: соединение обновляется раньше,
# чем его закроют на той стороне (урок черновика: pre-ping стоил 45 мс на каждое взятие).
POOL_RECYCLE_SECONDS: Final = 600
# Мёртвое соединение через WAN к дому RU обнаруживается за ≈ 60 с, а не после таймаута ОС.
TCP_KEEPALIVES: Final = MappingProxyType(
    {"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3}
)


@dataclass(frozen=True, slots=True)
class DatabaseProfile:
    """Pool and time limits of one process role (target architecture §4.3)."""

    pool_size: int
    statement_timeout: timedelta
    pool_timeout: timedelta = timedelta(seconds=2)


DATABASE_PROFILES: Final[Mapping[ProcessRole, DatabaseProfile]] = MappingProxyType(
    {
        ProcessRole.API: DatabaseProfile(pool_size=10, statement_timeout=timedelta(seconds=10)),
        ProcessRole.WS: DatabaseProfile(pool_size=2, statement_timeout=timedelta(seconds=10)),
        ProcessRole.WORKERS: DatabaseProfile(pool_size=5, statement_timeout=timedelta(seconds=60)),
        ProcessRole.SCHEDULER: DatabaseProfile(
            pool_size=2, statement_timeout=timedelta(seconds=10)
        ),
        # Разовые команды ИИ: пересборка читает суммы месяца по обоим домам.
        ProcessRole.AI: DatabaseProfile(pool_size=1, statement_timeout=timedelta(seconds=60)),
    }
)


def database_profile(role: ProcessRole) -> DatabaseProfile:
    """The profile of a long-running role; `migrate` works over its own direct connections."""
    profile = DATABASE_PROFILES.get(role)
    if profile is None:
        message = f"у роли {role} нет пулов приложения: миграции идут своими соединениями"
        raise ValueError(message)
    return profile


def engine_options(role: ProcessRole, profile: DatabaseProfile) -> dict[str, object]:
    """Pool and driver options of a role's engine: bounded, failing fast, nothing prepared."""
    return {
        "pool_size": profile.pool_size,
        "max_overflow": 0,
        "pool_timeout": profile.pool_timeout.total_seconds(),
        "pool_recycle": POOL_RECYCLE_SECONDS,
        "pool_pre_ping": False,
        # Значения параметров не попадают ни в текст исключения, ни в логи SQLAlchemy.
        "hide_parameters": True,
        "connect_args": {
            "prepare_threshold": None,
            "connect_timeout": CONNECT_TIMEOUT_SECONDS,
            "application_name": f"shosai-{role.value}",
            **TCP_KEEPALIVES,
        },
    }


def build_engine(url: SecretStr, role: ProcessRole, profile: DatabaseProfile) -> AsyncEngine:
    """An engine with a bounded pool that fails fast instead of queueing requests."""
    return create_async_engine(
        make_url(url.get_secret_value()).set(drivername=DRIVER), **engine_options(role, profile)
    )


class HomeDatabases:
    """The engines of every home in this process and the sessions opened on them."""

    def __init__(self, engines: Mapping[Home, AsyncEngine], profile: DatabaseProfile) -> None:
        missing = [home.value for home in Home if home not in engines]
        if missing:
            message = f"нет движков для домов: {', '.join(missing)}"
            raise ValueError(message)
        self.profile = profile
        self._engines = MappingProxyType(dict(engines))
        self._sessions = MappingProxyType(
            {
                home: async_sessionmaker(engine, expire_on_commit=False)
                for home, engine in engines.items()
            }
        )

    @classmethod
    def create(
        cls,
        urls: Mapping[Home, SecretStr],
        role: ProcessRole,
        *,
        profile: DatabaseProfile | None = None,
        tracer_provider: TracerProvider | None = None,
    ) -> Self:
        """One engine per home from the application-role addresses of the settings."""
        chosen = profile or database_profile(role)
        engines = {home: build_engine(url, role, chosen) for home, url in urls.items()}
        if tracer_provider is not None:
            for home, engine in engines.items():
                trace_statements(engine, home, tracer_provider)
        return cls(engines, chosen)

    def engine(self, home: Home) -> AsyncEngine:
        """The engine of a home."""
        return self._engines[home]

    def sessions(self, home: Home) -> async_sessionmaker[AsyncSession]:
        """The session factory of a home; `HomeTransactions` is the way to open one."""
        return self._sessions[home]

    async def dispose(self) -> None:
        """Close every pooled connection of every home; the first error is raised after all."""
        results = await asyncio.gather(
            *(engine.dispose() for engine in self._engines.values()), return_exceptions=True
        )
        for result in results:
            if isinstance(result, BaseException):
                raise result
