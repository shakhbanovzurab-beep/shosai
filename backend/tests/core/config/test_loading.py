"""Settings come only from the given mapping, are checked, and every problem is named."""

from ipaddress import ip_network
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic_settings import BaseSettings

from tests.core.config.sample_environ import (
    REQUIRED_VARIABLES,
    SAMPLE_FERNET_KEY,
    SAMPLE_SECRET,
    local_environ,
)
from whisperer.core.config.loading import ConfigurationError, _SectionReader, load_settings
from whisperer.core.config.values import Environment, LogLevel
from whisperer.core.kernel.homes import Home

SECRET_VARIABLES = (
    "HOME_RU_DATABASE_URL",
    "HOME_EU_MIGRATION_DATABASE_URL",
    "VALKEY_URL",
    "REDIS_CACHE_URL",
    "FERNET_KEY",
    "FERNET_KEYS_PREVIOUS",
)


def problems_of(environ: dict[str, str]) -> tuple[str, ...]:
    with pytest.raises(ConfigurationError) as raised:
        load_settings(environ)
    return raised.value.problems


def without(environ: dict[str, str], *names: str) -> dict[str, str]:
    return {name: value for name, value in environ.items() if name not in names}


def test_reads_every_section_of_a_local_environment() -> None:
    settings = load_settings(local_environ())

    assert settings.environment is Environment.DEVELOPMENT
    assert set(settings.homes) == set(Home)
    ru = settings.homes[Home.RU]
    assert ru.database_url.get_secret_value().endswith("@127.0.0.1:16432/whisperer")
    assert ru.s3_bucket == "whisperer-ru"
    assert settings.homes[Home.EU].s3_region == "local-eu"
    assert settings.shared_services.valkey_url.get_secret_value().endswith(":16379/0")
    assert settings.web.api_docs_enabled is False
    assert settings.web.cors_allowed_origins == ()
    assert settings.observability.log_level is LogLevel.INFO
    assert settings.observability.otel_exporter_otlp_endpoint is None
    assert settings.crypto.fernet_key is None


def test_secrets_are_masked_in_the_representation() -> None:
    assert SAMPLE_SECRET not in repr(load_settings(local_environ()))


def test_a_dotenv_file_in_the_working_directory_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = "\n".join(f"{name}={value}" for name, value in local_environ().items())
    (tmp_path / ".env").write_text(dotenv, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert set(problems_of({})) == {
        f"{name}: обязательная переменная не задана" for name in REQUIRED_VARIABLES
    }


def test_the_process_environment_is_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("REDIS_CACHE_URL", "redis://127.0.0.1:16380/0")

    problems = problems_of(without(local_environ(), "ENVIRONMENT", "REDIS_CACHE_URL"))

    assert problems == (
        "ENVIRONMENT: обязательная переменная не задана",
        "REDIS_CACHE_URL: обязательная переменная не задана",
    )


def test_an_empty_variable_counts_as_unset() -> None:
    assert problems_of(local_environ(HOME_EU_S3_BUCKET="")) == (
        "HOME_EU_S3_BUCKET: обязательная переменная не задана",
    )


def test_lists_are_comma_separated_and_normalized() -> None:
    settings = load_settings(
        local_environ(
            CORS_ALLOWED_ORIGINS="https://App.Example.com/, http://localhost:5173,,",
            TRUSTED_PROXY_ADDRESSES="10.0.0.0/24, 192.168.1.7, ::1",
            FERNET_KEY=SAMPLE_FERNET_KEY,
            FERNET_KEYS_PREVIOUS=f"{SAMPLE_FERNET_KEY}, {SAMPLE_FERNET_KEY}",
            LOG_LEVEL="warning",
            OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4318",
            API_DOCS_ENABLED="true",
        )
    )

    assert settings.web.cors_allowed_origins == (
        "https://app.example.com",
        "http://localhost:5173",
    )
    assert settings.web.trusted_proxy_addresses == (
        ip_network("10.0.0.0/24"),
        ip_network("192.168.1.7/32"),
        ip_network("::1/128"),
    )
    assert len(settings.crypto.fernet_keys_previous) == 2
    assert settings.observability.log_level is LogLevel.WARNING
    assert str(settings.observability.otel_exporter_otlp_endpoint) == "http://otel-collector:4318/"
    assert settings.web.api_docs_enabled is True


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("ENVIRONMENT", "prod"),
        ("HOME_RU_DATABASE_URL", "postgresql://whisperer_app:x@127.0.0.1/whisperer"),
        ("HOME_EU_DATABASE_URL", "postgresql+asyncpg://whisperer_app:x@127.0.0.1"),
        ("HOME_RU_S3_ENDPOINT_URL", "s3.example"),
        ("VALKEY_URL", "http://127.0.0.1:16379"),
        ("CORS_ALLOWED_ORIGINS", "*"),
        ("CORS_ALLOWED_ORIGINS", "https://app.example.com/path"),
        ("CORS_ALLOWED_ORIGINS", "https://app.example.com:port"),
        ("TRUSTED_PROXY_ADDRESSES", "*"),
        ("TRUSTED_PROXY_ADDRESSES", "edge.internal"),
        ("FERNET_KEY", "short"),
        ("FERNET_KEYS_PREVIOUS", f"{SAMPLE_FERNET_KEY},broken"),
        ("LOG_LEVEL", "TRACE"),
        ("API_DOCS_ENABLED", "sometimes"),
    ],
)
def test_an_invalid_value_is_refused_by_its_variable(variable: str, value: str) -> None:
    problems = problems_of(local_environ(**{variable: value}))

    assert problems
    assert all(problem.startswith(f"{variable}: ") for problem in problems)


@given(
    variable=st.sampled_from(SECRET_VARIABLES),
    secret=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=12, max_size=40),
)
def test_a_refusal_never_contains_the_value(variable: str, secret: str) -> None:
    marked = f"zq{secret}"
    environ = local_environ(**{variable: f"mysql://user:{marked}@{marked}/{marked}"})

    with pytest.raises(ConfigurationError) as raised:
        load_settings(environ)

    assert marked not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_a_json_value_that_does_not_parse_is_named_by_its_field() -> None:
    class WeightsSection(BaseSettings):
        """A section with a JSON-decoded field, as a slice might declare one."""

        weights: dict[str, int]

    reader = _SectionReader({"WEIGHTS": "{broken"})

    assert reader.read(WeightsSection, "") is None
    [problem] = reader.problems
    assert problem.startswith("WeightsSection: ")
    assert '"weights"' in problem
