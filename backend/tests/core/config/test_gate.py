"""A production process refuses to start on an unsafe configuration and names the setting."""

from collections.abc import Iterator

import pytest

from tests.core.config.sample_environ import SAMPLE_SECRET, local_environ, production_environ
from whisperer.core.config.gate import (
    GateViolation,
    UnsafeConfigurationError,
    enforce_production_gate,
)
from whisperer.core.config.loading import ConfigurationError, Settings, load_settings


def refusal(environ: dict[str, str]) -> str:
    """The message a process start gets: from loading the settings or from the gate."""
    with pytest.raises((ConfigurationError, UnsafeConfigurationError)) as raised:
        enforce_production_gate(load_settings(environ))
    return str(raised.value)


def without(environ: dict[str, str], *names: str) -> dict[str, str]:
    return {name: value for name, value in environ.items() if name not in names}


def test_a_safe_production_configuration_starts() -> None:
    enforce_production_gate(load_settings(production_environ()))


def test_outside_production_the_gate_does_not_apply() -> None:
    environ = local_environ(API_DOCS_ENABLED="true", LOG_LEVEL="DEBUG", ENVIRONMENT="staging")

    enforce_production_gate(load_settings(environ))


@pytest.mark.parametrize(
    ("environ", "setting"),
    [
        (production_environ(API_DOCS_ENABLED="true"), "API_DOCS_ENABLED"),
        (without(production_environ(), "TRUSTED_PROXY_ADDRESSES"), "TRUSTED_PROXY_ADDRESSES"),
        (without(production_environ(), "FERNET_KEY"), "FERNET_KEY"),
        (production_environ(CORS_ALLOWED_ORIGINS="*"), "CORS_ALLOWED_ORIGINS"),
        (without(production_environ(), "HOME_RU_DATABASE_URL"), "HOME_RU_DATABASE_URL"),
        (without(production_environ(), "HOME_EU_DATABASE_URL"), "HOME_EU_DATABASE_URL"),
        (without(production_environ(), "HOME_RU_S3_BUCKET"), "HOME_RU_S3_BUCKET"),
        (without(production_environ(), "HOME_EU_S3_BUCKET"), "HOME_EU_S3_BUCKET"),
        (production_environ(LOG_LEVEL="debug"), "LOG_LEVEL"),
        (
            production_environ(HOME_EU_S3_ENDPOINT_URL="http://s3.eu.example"),
            "HOME_EU_S3_ENDPOINT_URL",
        ),
        (without(production_environ(), "ENVIRONMENT"), "ENVIRONMENT"),
    ],
)
def test_each_unsafe_setting_refuses_start_and_is_named(
    environ: dict[str, str], setting: str
) -> None:
    message = refusal(environ)

    assert f"\n{setting}: " in message
    assert SAMPLE_SECRET not in message


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
