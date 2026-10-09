"""The harness guards refuse, before any write, a database that may not be a test one."""

from ipaddress import IPv4Address, IPv6Address

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.kernel.homes import Home
from tests.harness.guards import (
    UnsafeTestTargetError,
    ensure_prepared_test_database,
    ensure_safe_targets,
    is_loopback,
)
from tests.harness.sample_environ import SAMPLE_PASSWORD, sample_environ, sample_url
from tests.harness.settings import HarnessSettings


def check(environ: dict[str, str]) -> None:
    ensure_safe_targets(HarnessSettings.from_environ(environ), environ)


def test_accepts_the_local_test_databases() -> None:
    check(sample_environ())


def test_refuses_the_home_database_shosai() -> None:
    environ = sample_environ(
        TEST_HOME_RU_DATABASE_URL=sample_url("shosai_app", 16432, database="shosai")
    )

    with pytest.raises(UnsafeTestTargetError, match="имя базы shosai, ожидается") as raised:
        check(environ)

    assert "TEST_HOME_RU_DATABASE_URL" in str(raised.value)


@pytest.mark.parametrize("host", ["10.0.0.5", "192.168.1.10", "db.example.com", "postgres-eu"])
def test_refuses_a_host_that_is_not_loopback(host: str) -> None:
    environ = sample_environ(
        TEST_HOME_EU_MIGRATION_DATABASE_URL=sample_url("shosai_migrator", 5432, host=host)
    )

    with pytest.raises(UnsafeTestTargetError, match=f"хост {host} не петлевой") as raised:
        check(environ)

    assert "TEST_HOME_EU_MIGRATION_DATABASE_URL" in str(raised.value)


def test_refuses_a_test_url_equal_to_a_runtime_url() -> None:
    environ = sample_environ()
    environ["HOME_EU_DATABASE_URL"] = environ["TEST_HOME_EU_DATABASE_URL"]

    with pytest.raises(UnsafeTestTargetError, match="TEST_HOME_EU_DATABASE_URL: совпадает"):
        check(environ)


def test_reports_every_problem_at_once_without_passwords() -> None:
    environ = sample_environ(
        TEST_HOME_RU_DATABASE_URL=sample_url("shosai_app", 5432, host="10.0.0.5"),
        TEST_HOME_EU_DATABASE_URL=sample_url("shosai_app", 5432, database="shosai"),
    )

    with pytest.raises(UnsafeTestTargetError) as raised:
        check(environ)

    message = str(raised.value)
    assert "TEST_HOME_RU_DATABASE_URL: хост" in message
    assert "TEST_HOME_EU_DATABASE_URL: имя базы" in message
    assert SAMPLE_PASSWORD not in message


@given(st.ip_addresses())
def test_loopback_follows_ip_semantics(address: IPv4Address | IPv6Address) -> None:
    assert is_loopback(str(address)) == address.is_loopback


def test_localhost_is_the_only_loopback_name() -> None:
    assert is_loopback("localhost")
    assert not is_loopback("localhost.example.com")
    assert not is_loopback("postgres-ru")


def test_accepts_only_a_database_prepared_for_tests() -> None:
    target = HarnessSettings.from_environ(sample_environ()).homes[Home.RU].migration.for_slot(1)

    ensure_prepared_test_database(target, "Prepared test database 1 of the Russian home (local)")
    for comment in (None, "Shosai Russian home (local)", ""):
        with pytest.raises(UnsafeTestTargetError, match="shosai_test_1"):
            ensure_prepared_test_database(target, comment)
