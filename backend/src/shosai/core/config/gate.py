"""Production gate: a staging or production process refuses to start on an unsafe configuration.

The draft once ran production with `ENVIRONMENT` unset and every safety check silently off;
here `ENVIRONMENT` is required and the gate names each unsafe setting, never its value.
Staging runs under the same gate, API docs included: it is reachable from the internet and
holds real-shaped data (F1 audit OD-7). Only development, local and in tests, is exempt.
A slice adds its own checks (for example, billing dev mode) through `extra_checks`.
"""

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import Final
from urllib.parse import urlsplit

from shosai.core.config.loading import Settings
from shosai.core.config.sections import SmtpSecurity, home_prefix
from shosai.core.config.values import Environment, LogLevel, database_url_parameter

SECURE_STORAGE_SCHEME = "https"
# Управляемый Valkey стоит вне контейнеров плоскости: задачи, строки транскрипта и
# состояние встреч идут к нему по сети провайдера (решение владельца F1-D12).
SECURE_VALKEY_SCHEME = "rediss"
# Управляемый Valkey в Timeweb не даёт TLS (ADR 0042): открытый протокол допустим только к
# IP-адресу приватной сети. Имя хоста не годится — куда оно разрешится, при старте не проверить.
PLAIN_VALKEY_SCHEME = "redis"
MIN_LINK_SECRET_LENGTH: Final = 32
PRIVATE_NETWORKS: Final = tuple(
    ip_network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)
# Дом RU — в другой юрисдикции и за 45 мс по сети (§4.1): без проверки сертификата и
# имени сервера соединение можно перехватить на пути.
SECURE_DATABASE_SSLMODE = "verify-full"


@dataclass(frozen=True, slots=True)
class GateViolation:
    """One unsafe setting: the variable name and why production cannot run with it."""

    setting: str
    reason: str


type ProductionCheck = Callable[[Settings], Iterable[GateViolation]]


class UnsafeConfigurationError(Exception):
    """A staging or production process would start with an unsafe configuration."""

    def __init__(self, environment: Environment, violations: Sequence[GateViolation]) -> None:
        self.environment = environment
        self.violations = tuple(violations)
        lines = [f"{violation.setting}: {violation.reason}" for violation in violations]
        super().__init__(
            f"Среда {environment.value} не запускается с такими настройками:\n" + "\n".join(lines)
        )


def enforce_production_gate(
    settings: Settings, extra_checks: Sequence[ProductionCheck] = ()
) -> None:
    """Raise `UnsafeConfigurationError` listing every violation; in development, do nothing."""
    if not settings.environment.is_gated:
        return
    violations = [
        violation for check in (*CORE_CHECKS, *extra_checks) for violation in check(settings)
    ]
    if violations:
        raise UnsafeConfigurationError(settings.environment, violations)


def api_docs_closed(settings: Settings) -> Iterator[GateViolation]:
    """API docs reveal the whole admin and billing schema."""
    if settings.web.api_docs_enabled:
        yield GateViolation("API_DOCS_ENABLED", "документация API выключена вне разработки")


def proxies_trusted(settings: Settings) -> Iterator[GateViolation]:
    """Behind the edge, the client address is known only from a trusted proxy's header."""
    if not settings.web.trusted_proxy_addresses:
        yield GateViolation(
            "TRUSTED_PROXY_ADDRESSES",
            "нужны адреса edge: без них лимиты и аудит видят адрес прокси вместо клиента",
        )


def encryption_key_present(settings: Settings) -> Iterator[GateViolation]:
    """Stored credentials of integrations are encrypted with the Fernet key ring."""
    if settings.crypto.fernet_key is None:
        yield GateViolation("FERNET_KEY", "без ключа хранимые учётные данные не расшифровать")


def debug_logs_off(settings: Settings) -> Iterator[GateViolation]:
    """DEBUG is switched on only for one company or user for a limited time (§16.7)."""
    if settings.observability.log_level is LogLevel.DEBUG:
        yield GateViolation("LOG_LEVEL", "DEBUG для всего процесса вне разработки запрещён")


def storage_over_tls(settings: Settings) -> Iterator[GateViolation]:
    """Files and their signed links travel to each home's bucket only over TLS (ADR 0044)."""
    for home, storage in settings.storage.items():
        if storage.s3_endpoint_url.scheme != SECURE_STORAGE_SCHEME:
            yield GateViolation(
                f"{home_prefix(home)}S3_ENDPOINT_URL", "к хранилищу вне разработки — только https"
            )


def valkey_link_protected(settings: Settings) -> Iterator[GateViolation]:
    """Valkey is reached over TLS, or in plain text only at a private-network address (ADR 0042).

    Task payloads, transcript lines and meeting state travel this link; outside the private
    network nothing but TLS protects them.
    """
    parts = urlsplit(settings.shared_services.valkey_url.get_secret_value())
    if parts.scheme == SECURE_VALKEY_SCHEME:
        return
    if parts.scheme == PLAIN_VALKEY_SCHEME and is_private_address(parts.hostname):
        return
    yield GateViolation(
        "VALKEY_URL",
        f"к Valkey вне разработки — {SECURE_VALKEY_SCHEME}:// "
        f"или {PLAIN_VALKEY_SCHEME}:// на IP-адрес приватной сети",
    )


def is_private_address(host: str | None) -> bool:
    """Whether the host is an IP literal of a private network (RFC 1918, RFC 4193)."""
    if host is None:
        return False
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in PRIVATE_NETWORKS)


def ai_provider_keys_present(settings: Settings) -> Iterator[GateViolation]:
    """Every AI provider the product needs has its key; presence of a key is not a decision."""
    if settings.ai.openrouter_api_key is None:
        yield GateViolation("OPENROUTER_API_KEY", "без ключа OpenRouter модели недоступны")
    if settings.ai.pyannote_api_key is None:
        yield GateViolation("PYANNOTE_API_KEY", "без ключа pyannote записи встреч без говорящих")
    if settings.ai.openai_api_key is None:
        yield GateViolation("OPENAI_API_KEY", "без ключа OpenAI нет потоковой расшифровки")
    if settings.ai.google_live_api_key is None:
        yield GateViolation("GOOGLE_LIVE_API_KEY", "без ключа Gemini нет перевода и голоса")
    if settings.ai.mistral_api_key is None:
        yield GateViolation("MISTRAL_API_KEY", "без ключа Mistral сканы документов не читаются")


def mail_over_tls(settings: Settings) -> Iterator[GateViolation]:
    """Mail leaves over TLS from both authenticated mailboxes (F6 plan §3.8)."""
    email = settings.email
    if email.smtp_security is SmtpSecurity.NONE:
        yield GateViolation("SMTP_SECURITY", "вне разработки почта уходит только по TLS")
    for prefix, user, password in (
        ("SMTP_ACCOUNT", email.smtp_account_user, email.smtp_account_password),
        ("SMTP_NOTIFICATIONS", email.smtp_notifications_user, email.smtp_notifications_password),
    ):
        if not user or password is None:
            yield GateViolation(f"{prefix}_USER", "без ящика и пароля письма этого вида не уйдут")
    secret = email.email_link_secret
    if secret is None or len(secret.get_secret_value()) < MIN_LINK_SECRET_LENGTH:
        yield GateViolation(
            "EMAIL_LINK_SECRET", "ссылки отписки подписываются секретом не короче 32 символов"
        )


def databases_over_tls(settings: Settings) -> Iterator[GateViolation]:
    """Each home's database is reached over TLS that checks the certificate and the host."""
    for home, home_settings in settings.homes.items():
        addresses = {
            "DATABASE_URL": home_settings.database_url,
            "MIGRATION_DATABASE_URL": home_settings.migration_database_url,
        }
        for name, url in addresses.items():
            if url is None:
                continue
            if database_url_parameter(url, "sslmode") != SECURE_DATABASE_SSLMODE:
                yield GateViolation(
                    f"{home_prefix(home)}{name}",
                    f"к базе дома вне разработки — только sslmode={SECURE_DATABASE_SSLMODE}",
                )


CORE_CHECKS: tuple[ProductionCheck, ...] = (
    api_docs_closed,
    proxies_trusted,
    encryption_key_present,
    debug_logs_off,
    storage_over_tls,
    valkey_link_protected,
    databases_over_tls,
    ai_provider_keys_present,
    mail_over_tls,
)
