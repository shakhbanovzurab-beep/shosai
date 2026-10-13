"""A staging or production process refuses to start on an unsafe configuration and names it."""

from collections.abc import Iterator

import pytest

from shosai.core.config.gate import (
    GateViolation,
    UnsafeConfigurationError,
    enforce_production_gate,
)
from shosai.core.config.loading import ConfigurationError, Settings, load_settings
from shosai.core.kernel.homes import Home
from tests.core.config.sample_environ import (
    SAMPLE_SECRET,
    local_environ,
    production_database_url,
    production_environ,
)


def refusal(environ: dict[str, str]) -> str:
    """The message a process start gets: from loading the settings or from the gate."""
    with pytest.raises((ConfigurationError, UnsafeConfigurationError)) as raised:
        enforce_production_gate(load_settings(environ))
    return str(raised.value)


def without(environ: dict[str, str], *names: str) -> dict[str, str]:
    return {name: value for name, value in environ.items() if name not in names}


def test_a_safe_production_configuration_starts() -> None:
    enforce_production_gate(load_settings(production_environ()))


def test_in_development_the_gate_does_not_apply() -> None:
    environ = local_environ(API_DOCS_ENABLED="true", LOG_LEVEL="DEBUG")

    enforce_production_gate(load_settings(environ))


def test_a_safe_staging_configuration_starts() -> None:
    enforce_production_gate(load_settings(production_environ(ENVIRONMENT="staging")))


@pytest.mark.parametrize(
    ("unsafe", "setting"),
    [
        ({"API_DOCS_ENABLED": "true"}, "API_DOCS_ENABLED"),
        ({"LOG_LEVEL": "DEBUG"}, "LOG_LEVEL"),
        ({"S3_ENDPOINT_URL": "http://s3.ru.example"}, "S3_ENDPOINT_URL"),
        ({"VALKEY_URL": f"redis://:{SAMPLE_SECRET}@valkey.eu.example:6379/0"}, "VALKEY_URL"),
        (
            {"HOME_RU_DATABASE_URL": f"postgresql://shosai_app:{SAMPLE_SECRET}@db.ru/shosai"},
            "HOME_RU_DATABASE_URL",
        ),
    ],
)
def test_staging_runs_under_the_same_gate_and_names_the_setting(
    unsafe: dict[str, str], setting: str
) -> None:
    environ = production_environ(ENVIRONMENT="staging", **unsafe)

    with pytest.raises(UnsafeConfigurationError) as raised:
        enforce_production_gate(load_settings(environ))

    message = str(raised.value)
    assert message.startswith("Среда staging не запускается")
    assert f"\n{setting}: " in message
    assert SAMPLE_SECRET not in message


def test_staging_without_trusted_proxies_refuses_start() -> None:
    environ = without(production_environ(ENVIRONMENT="staging"), "TRUSTED_PROXY_ADDRESSES")

    assert "\nTRUSTED_PROXY_ADDRESSES: " in refusal(environ)


@pytest.mark.parametrize(
    ("environ", "setting"),
    [
        (production_environ(API_DOCS_ENABLED="true"), "API_DOCS_ENABLED"),
        (without(production_environ(), "TRUSTED_PROXY_ADDRESSES"), "TRUSTED_PROXY_ADDRESSES"),
        (without(production_environ(), "FERNET_KEY"), "FERNET_KEY"),
        (without(production_environ(), "OPENROUTER_API_KEY"), "OPENROUTER_API_KEY"),
        (production_environ(CORS_ALLOWED_ORIGINS="*"), "CORS_ALLOWED_ORIGINS"),
        (without(production_environ(), "HOME_RU_DATABASE_URL"), "HOME_RU_DATABASE_URL"),
        (without(production_environ(), "HOME_EU_DATABASE_URL"), "HOME_EU_DATABASE_URL"),
        (without(production_environ(), "S3_BUCKET"), "S3_BUCKET"),
        (without(production_environ(), "VALKEY_URL"), "VALKEY_URL"),
        (production_environ(LOG_LEVEL="debug"), "LOG_LEVEL"),
        (production_environ(S3_ENDPOINT_URL="http://s3.ru.example"), "S3_ENDPOINT_URL"),
        (
            production_environ(VALKEY_URL=f"redis://:{SAMPLE_SECRET}@valkey.eu.example:6379/0"),
            "VALKEY_URL",
        ),
        (without(production_environ(), "ENVIRONMENT"), "ENVIRONMENT"),
        (
            production_environ(
                HOME_RU_DATABASE_URL=production_database_url(Home.RU).replace(
                    "verify-full", "require"
                )
            ),
            "HOME_RU_DATABASE_URL",
        ),
        (
            production_environ(
                HOME_EU_DATABASE_URL=f"postgresql://shosai_app:{SAMPLE_SECRET}@db.eu/shosai"
            ),
            "HOME_EU_DATABASE_URL",
        ),
        (
            production_environ(
                HOME_EU_MIGRATION_DATABASE_URL=(
                    f"postgresql://shosai_migrator:{SAMPLE_SECRET}@db.eu/shosai?sslmode=prefer"
                )
            ),
            "HOME_EU_MIGRATION_DATABASE_URL",
        ),
    ],
)
def test_each_unsafe_setting_refuses_start_and_is_named(
    environ: dict[str, str], setting: str
) -> None:
    message = refusal(environ)

    assert f"\n{setting}: " in message
    assert SAMPLE_SECRET not in message


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize(
    "host", ["192.168.0.8", "10.20.30.40", "172.16.5.6", "172.31.255.1", "[fd12:3456::8]"]
)
def test_valkey_without_tls_passes_only_at_a_private_address(environment: str, host: str) -> None:
    environ = production_environ(
        ENVIRONMENT=environment, VALKEY_URL=f"redis://default:{SAMPLE_SECRET}@{host}:6379/0"
    )

    enforce_production_gate(load_settings(environ))


@pytest.mark.parametrize(
    "host", ["valkey.internal", "8.8.8.8", "127.0.0.1", "172.32.0.1", "[2001:db8::1]"]
)
def test_valkey_without_tls_at_any_other_address_refuses_start(host: str) -> None:
    environ = production_environ(VALKEY_URL=f"redis://default:{SAMPLE_SECRET}@{host}:6379/0")

    message = refusal(environ)

    assert "\nVALKEY_URL: " in message
    assert SAMPLE_SECRET not in message


def test_a_migration_address_with_verified_tls_passes() -> None:
    environ = production_environ(
        HOME_RU_MIGRATION_DATABASE_URL=production_database_url(Home.RU, role="shosai_migrator")
    )

    enforce_production_gate(load_settings(environ))


def test_every_violation_is_reported_at_once() -> None:
    environ = without(
        production_environ(API_DOCS_ENABLED="true", LOG_LEVEL="DEBUG"),
        "FERNET_KEY",
        "TRUSTED_PROXY_ADDRESSES",
    )

    with pytest.raises(UnsafeConfigurationError) as raised:
        enforce_production_gate(load_settings(environ))

    assert [violation.setting for violation in raised.value.violations] == [
        "API_DOCS_ENABLED",
        "TRUSTED_PROXY_ADDRESSES",
        "FERNET_KEY",
        "LOG_LEVEL",
    ]


def test_a_slice_adds_its_own_check() -> None:
    def billing_live_mode(_settings: Settings) -> Iterator[GateViolation]:
        yield GateViolation("BILLING_DEV_MODE", "в production платежи настоящие")

    with pytest.raises(UnsafeConfigurationError) as raised:
        enforce_production_gate(load_settings(production_environ()), [billing_live_mode])

    assert raised.value.violations == (
        GateViolation("BILLING_DEV_MODE", "в production платежи настоящие"),
    )
