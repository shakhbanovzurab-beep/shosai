"""Engines per home: the pool and time limits of each role, the driver and its settings."""

from datetime import timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy.pool import QueuePool

from shosai.core.config.roles import ProcessRole
from shosai.core.db.engines import (
    DRIVER,
    POOL_RECYCLE_SECONDS,
    DatabaseProfile,
    HomeDatabases,
    build_engine,
    database_profile,
    engine_options,
)
from shosai.core.kernel.homes import Home

URL = SecretStr(
    "postgresql://shosai_app:sample-secret@db.ru.example:6432/shosai"
    "?sslmode=verify-full&sslrootcert=system"
)


@pytest.mark.parametrize(
    ("role", "pool_size", "statement_timeout"),
    [
        (ProcessRole.API, 10, timedelta(seconds=10)),
        (ProcessRole.WS, 2, timedelta(seconds=10)),
        (ProcessRole.WORKERS, 5, timedelta(seconds=60)),
        (ProcessRole.SCHEDULER, 2, timedelta(seconds=10)),
    ],
)
def test_each_role_has_the_limits_of_section_4_3(
    role: ProcessRole, pool_size: int, statement_timeout: timedelta
) -> None:
    profile = database_profile(role)

    assert (profile.pool_size, profile.statement_timeout) == (pool_size, statement_timeout)
    assert profile.pool_timeout == timedelta(seconds=2)


def test_the_migrate_command_has_no_application_pools() -> None:
    with pytest.raises(ValueError, match="нет пулов приложения"):
        database_profile(ProcessRole.MIGRATE)


def test_a_pool_is_bounded_fails_fast_and_prepares_nothing() -> None:
    options = engine_options(ProcessRole.WORKERS, database_profile(ProcessRole.WORKERS))

    assert {name: options[name] for name in ("pool_size", "max_overflow", "pool_timeout")} == {
        "pool_size": 5,
        "max_overflow": 0,
        "pool_timeout": 2.0,
    }
    assert options["pool_recycle"] == POOL_RECYCLE_SECONDS
    assert options["pool_pre_ping"] is False
    assert options["hide_parameters"] is True
    assert options["connect_args"] == {
        "prepare_threshold": None,
        "connect_timeout": 5,
        "application_name": "shosai-workers",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }


async def test_an_engine_takes_the_driver_and_keeps_the_tls_of_the_address() -> None:
    engine = build_engine(URL, ProcessRole.API, database_profile(ProcessRole.API))
    try:
        _, connect_args = engine.dialect.create_connect_args(engine.url)
        pool = engine.pool
        assert engine.url.drivername == DRIVER
        assert isinstance(pool, QueuePool)
        assert (pool.size(), pool.timeout()) == (10, 2.0)
        assert (connect_args["sslmode"], connect_args["sslrootcert"]) == ("verify-full", "system")
        assert "sample-secret" not in repr(engine.url)
    finally:
        await engine.dispose()


async def test_a_process_has_exactly_one_engine_per_home() -> None:
    profile = DatabaseProfile(pool_size=1, statement_timeout=timedelta(seconds=1))
    databases = HomeDatabases.create(dict.fromkeys(Home, URL), ProcessRole.API, profile=profile)
    try:
        engines = {home: databases.engine(home) for home in Home}
        assert len({id(engine) for engine in engines.values()}) == len(Home)
        assert databases.profile is profile
    finally:
        await databases.dispose()


def test_databases_without_a_home_are_refused() -> None:
    engine = build_engine(URL, ProcessRole.API, database_profile(ProcessRole.API))

    with pytest.raises(ValueError, match="нет движков для домов: eu"):
        HomeDatabases({Home.RU: engine}, database_profile(ProcessRole.API))
