"""Settings sections; each is read from environment variables with its own prefix.

`.env.example` section 2 documents every variable with its purpose. A section never reads
a dotenv file: `env_file` is off, and an empty variable counts as unset.
"""

from ipaddress import IPv4Address
from typing import Self

from pydantic import HttpUrl, IPvAnyAddress, SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from whisperer.core.config.values import (
    DatabaseUrl,
    Environment,
    FernetKey,
    FernetKeys,
    LogLevel,
    LogLevelName,
    NonEmptyText,
    Origins,
    Port,
    ProxyNetworks,
    RedisUrl,
)
from whisperer.core.kernel.homes import Home


def home_prefix(home: Home) -> str:
    """Prefix of a home's variables: `HOME_RU_`, `HOME_EU_`."""
    return f"HOME_{home.name}_"


class SettingsSection(BaseSettings):
    """A section validated only from the values `load_settings` passes in.

    pydantic validates a settings model through its `__init__`, which would otherwise
    fill missing fields from the process environment and break an explicit mapping.
    """

    model_config = SettingsConfigDict(
        env_file=None,
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Only the values given to the constructor; no environment, dotenv or secret files."""
        return (init_settings,)


class RuntimeSettings(SettingsSection):
    """Where the process runs. `ENVIRONMENT` has no default: unset, the process stops."""

    environment: Environment


class HomeSettings(SettingsSection):
    """One data home: its PostgreSQL behind PgBouncer (`HOME_<RU|EU>_*`).

    The migration address is only for the `migrate` command: the long-running roles work
    under the application role and do not receive the owner's password.
    """

    database_url: DatabaseUrl
    migration_database_url: DatabaseUrl | None = None


class StorageSettings(SettingsSection):
    """The one S3 bucket in Russia: files of both homes and of the platform (ADR 0014)."""

    s3_endpoint_url: HttpUrl
    s3_region: NonEmptyText
    s3_bucket: NonEmptyText
    s3_access_key_id: NonEmptyText
    s3_secret_access_key: SecretStr


class SharedServicesSettings(SettingsSection):
    """Services of the compute plane: Valkey for tasks, queues and locks; the LRU cache."""

    valkey_url: RedisUrl
    redis_cache_url: RedisUrl


class WebSettings(SettingsSection):
    """The HTTP surface: API docs, the CORS allowlist and the proxies trusted for client IPs."""

    api_docs_enabled: bool = False
    cors_allowed_origins: Origins = ()
    trusted_proxy_addresses: ProxyNetworks = ()


class ServerSettings(SettingsSection):
    """Where a process listens: the public port of `api` and `ws` and the ops port of every role.

    The ops port serves liveness, readiness and metrics; the edge never proxies it (F1-C3).
    """

    bind_host: IPvAnyAddress = IPv4Address("127.0.0.1")
    http_port: Port = 8000
    ops_port: Port = 9100

    @model_validator(mode="after")
    def ports_differ(self) -> Self:
        """The public and the ops server cannot share a port."""
        if self.http_port == self.ops_port:
            message = "HTTP_PORT и OPS_PORT совпадают"
            raise ValueError(message)
        return self


class ObservabilitySettings(SettingsSection):
    """Logs and traces: the log level and the OpenTelemetry collector, if any."""

    log_level: LogLevelName = LogLevel.INFO
    # Базовый адрес коллектора OTLP/HTTP, как в стандартной переменной OpenTelemetry;
    # путь /v1/traces добавляет экспортёр. Не задан — спаны никуда не отправляются.
    otel_exporter_otlp_endpoint: HttpUrl | None = None
    otel_service_name: NonEmptyText = "whisperer"


class CryptoSettings(SettingsSection):
    """The Fernet key ring: the active key encrypts, previous keys only decrypt."""

    fernet_key: FernetKey | None = None
    fernet_keys_previous: FernetKeys = ()
