"""Settings sections; each is read from environment variables with its own prefix.

`.env.example` section 2 documents every variable with its purpose. A section never reads
a dotenv file: `env_file` is off, and an empty variable counts as unset.
"""

from decimal import Decimal
from ipaddress import IPv4Address
from typing import Self

from pydantic import (
    Field,
    HttpUrl,
    IPvAnyAddress,
    PositiveInt,
    SecretStr,
    WebsocketUrl,
    model_validator,
)
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from shosai.core.config.values import (
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
from shosai.core.kernel.homes import Home


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
    otel_service_name: NonEmptyText = "shosai"


class CryptoSettings(SettingsSection):
    """The Fernet key ring: the active key encrypts, previous keys only decrypt."""

    fernet_key: FernetKey | None = None
    fernet_keys_previous: FernetKeys = ()


class AiSettings(SettingsSection):
    """The AI providers: credentials and addresses of each (F6 plan §3.12)."""

    # Без ключа провайдер выключен явно: вызов отклоняется, вне разработки гейт не пускает.
    openrouter_api_key: SecretStr | None = None
    # Пусто — адрес провайдера из адаптера: хосты провайдеров названы только в core/ai.
    openrouter_base_url: HttpUrl | None = None
    # Ключ управления OpenRouter: только для отчёта о балансе; без него баланс неизвестен.
    openrouter_management_key: SecretStr | None = None
    # Разметка говорящих в записях встреч; без ключа вызовы diarize отклоняются.
    pyannote_api_key: SecretStr | None = None
    pyannote_base_url: HttpUrl | None = None
    # Потоковая расшифровка живой встречи моделями OpenAI Realtime.
    openai_api_key: SecretStr | None = None
    openai_realtime_url: WebsocketUrl | None = None
    # Gemini Live: синхронный перевод и голосовой ассистент.
    google_live_api_key: SecretStr | None = None
    google_live_base_url: HttpUrl | None = None
    # Mistral OCR: сканы и картинки документов.
    mistral_api_key: SecretStr | None = None
    mistral_base_url: HttpUrl | None = None
    # Вызовы и сессии в полёте на провайдера по всему плану (§3.5): ниже его квоты.
    openrouter_slots: PositiveInt = 292
    pyannote_slots: PositiveInt = 16
    mistral_slots: PositiveInt = 16
    openai_realtime_slots: PositiveInt = 1000
    google_live_slots: PositiveInt = 1000


class SpendSettings(SettingsSection):
    """The platform's own spend ceilings and the kill switch (§3.6, F6-C19).

    The user's ceilings come from the caller with each call (the plan's limits); these are
    the platform's: global per hour and day, and per platform account. None stops an
    essential call (inv-13).
    """

    ai_global_hourly_usd: Decimal = Field(default=Decimal(400), ge=0)
    ai_global_daily_usd: Decimal = Field(default=Decimal(4000), ge=0)
    ai_landing_demo_hourly_usd: Decimal = Field(default=Decimal(5), ge=0)
    ai_landing_demo_daily_usd: Decimal = Field(default=Decimal(20), ge=0)
    ai_help_assistant_hourly_usd: Decimal = Field(default=Decimal(5), ge=0)
    ai_help_assistant_daily_usd: Decimal = Field(default=Decimal(20), ge=0)
    ai_system_hourly_usd: Decimal = Field(default=Decimal(10), ge=0)
    ai_system_daily_usd: Decimal = Field(default=Decimal(50), ge=0)
    # Включён настройкой — дорогие вызовы стоят, что бы ни лежало в Valkey.
    ai_kill_switch: bool = False
    # Резерв, не снятый вовремя (процесс умер), освобождается по окончании аренды.
    ai_reservation_lease_seconds: PositiveInt = 300
    # Траты пользователя за сутки, после которых оператор получает событие; 0 — не следить.
    ai_user_daily_alert_usd: Decimal = Field(default=Decimal(20), ge=0)


class AiGuardSettings(SettingsSection):
    """Per-user guards that need no calibration (F6-D6, §3.7)."""

    # Интерактивных потоков и сессий одного пользователя одновременно (F6-C20).
    ai_interactive_streams: PositiveInt = 2
    ai_max_context_tokens: PositiveInt = 32_000
    ai_max_images: PositiveInt = 6
    ai_max_image_mb: PositiveInt = 8


class ExchangeRateSettings(SettingsSection):
    """Where the Central Bank's daily rates are read (ADR 0036)."""

    cbr_daily_url: HttpUrl = HttpUrl("https://www.cbr-xml-daily.ru/daily_json.js")
