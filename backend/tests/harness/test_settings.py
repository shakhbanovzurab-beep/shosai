"""Harness settings come only from TEST_* and never reveal passwords."""

import pytest

from tests.harness.sample_environ import SAMPLE_PASSWORD, sample_environ, sample_url
from tests.harness.settings import (
    DatabaseTarget,
    HarnessConfigurationError,
    HarnessSettings,
    application_variable,
    migration_variable,
)
from whisperer.core.kernel.homes import Home

ALL_DATABASE_VARIABLES = [
    variable(home) for home in Home for variable in (application_variable, migration_variable)
]


def test_reads_both_roles_of_both_homes_and_the_slot_count() -> None:
    settings = HarnessSettings.from_environ(sample_environ())

    assert settings.homes[Home.RU].application == DatabaseTarget(
        variable="TEST_HOME_RU_DATABASE_URL",
        host="127.0.0.1",
        port=16432,
        user="whisperer_app",
        password=SAMPLE_PASSWORD,
        database="whisperer_test",
    )
    assert settings.homes[Home.EU].migration.port == 15433
    assert settings.homes[Home.EU].migration.user == "whisperer_migrator"
    assert settings.database_slots == 8
    assert sorted(settings.database_variables()) == sorted(ALL_DATABASE_VARIABLES)


def test_never_falls_back_to_runtime_variables() -> None:
    runtime_only = {
        "HOME_RU_DATABASE_URL": sample_url("whisperer_app", 16432, database="whisperer"),
        "DATABASE_URL": sample_url("whisperer_app", 16432, database="whisperer"),
    }

    with pytest.raises(HarnessConfigurationError) as raised:
        HarnessSettings.from_environ(runtime_only)

    message = str(raised.value)
    for variable in [*ALL_DATABASE_VARIABLES, "TEST_DATABASE_SLOTS"]:
        assert f"{variable}: не задана" in message
    assert ".env.example" in message


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("postgresql://u:p@127.0.0.1:5432/whisperer_test", "схема адреса"),
        ("postgresql+asyncpg://u:p@127.0.0.1:5432/whisperer_test?ssl=require", "параметры"),
        ("postgresql+asyncpg://u@127.0.0.1:5432/whisperer_test", "пароль"),
        ("postgresql+asyncpg://u:p@127.0.0.1:port/whisperer_test", "порт"),
    ],
)
def test_rejects_a_malformed_url_naming_the_variable(url: str, reason: str) -> None:
    environ = sample_environ(TEST_HOME_EU_MIGRATION_DATABASE_URL=url)

    with pytest.raises(HarnessConfigurationError, match=reason) as raised:
        HarnessSettings.from_environ(environ)

    assert "TEST_HOME_EU_MIGRATION_DATABASE_URL" in str(raised.value)


@pytest.mark.parametrize("raw", ["0", "16", "-1", "eight", "8.0"])
def test_rejects_a_slot_count_outside_valkey_databases(raw: str) -> None:
    with pytest.raises(HarnessConfigurationError, match="от 1 до 15"):
        HarnessSettings.from_environ(sample_environ(TEST_DATABASE_SLOTS=raw))


def test_password_stays_out_of_errors_and_repr() -> None:
    broken = f"mysql://whisperer_app:{SAMPLE_PASSWORD}@127.0.0.1:3306/whisperer_test"
    with pytest.raises(HarnessConfigurationError) as raised:
        HarnessSettings.from_environ(sample_environ(TEST_HOME_RU_DATABASE_URL=broken))

    target = HarnessSettings.from_environ(sample_environ()).homes[Home.RU].application
    assert SAMPLE_PASSWORD not in str(raised.value)
    assert SAMPLE_PASSWORD not in repr(target)


def test_decodes_credentials_and_reads_ipv6_hosts() -> None:
    url = "postgresql+asyncpg://who%40ever:p%2Fss@[::1]:16432/whisperer_test"

    target = (
        HarnessSettings.from_environ(sample_environ(TEST_HOME_RU_DATABASE_URL=url))
        .homes[Home.RU]
        .application
    )

    assert (target.host, target.user, target.password) == ("::1", "who@ever", "p/ss")


def test_slot_target_appends_the_slot_number() -> None:
    target = HarnessSettings.from_environ(sample_environ()).homes[Home.RU].migration

    slot_target = target.for_slot(3)

    assert slot_target.database == "whisperer_test_3"
    assert (slot_target.host, slot_target.port, slot_target.user) == (
        target.host,
        target.port,
        target.user,
    )
