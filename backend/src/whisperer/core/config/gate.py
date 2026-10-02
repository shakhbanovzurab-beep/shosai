"""Production gate: a production process refuses to start on an unsafe configuration.

The draft once ran production with `ENVIRONMENT` unset and every safety check silently off;
here `ENVIRONMENT` is required and the gate names each unsafe setting, never its value.
A slice adds its own checks (for example, billing dev mode) through `extra_checks`.
"""

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass

from whisperer.core.config.loading import Settings
from whisperer.core.config.sections import home_prefix
from whisperer.core.config.values import Environment, LogLevel

SECURE_STORAGE_SCHEME = "https"


@dataclass(frozen=True, slots=True)
class GateViolation:
    """One unsafe setting: the variable name and why production cannot run with it."""

    setting: str
    reason: str


type ProductionCheck = Callable[[Settings], Iterable[GateViolation]]


class UnsafeConfigurationError(Exception):
    """A production process would start with an unsafe configuration."""

    def __init__(self, violations: Sequence[GateViolation]) -> None:
        self.violations = tuple(violations)
        lines = [f"{violation.setting}: {violation.reason}" for violation in violations]
        super().__init__("Production не запускается с такими настройками:\n" + "\n".join(lines))


def enforce_production_gate(
    settings: Settings, extra_checks: Sequence[ProductionCheck] = ()
) -> None:
    """Raise `UnsafeConfigurationError` listing every violation; outside production, do nothing."""
    if settings.environment is not Environment.PRODUCTION:
        return
    violations = [
        violation for check in (*CORE_CHECKS, *extra_checks) for violation in check(settings)
    ]
    if violations:
        raise UnsafeConfigurationError(violations)


def api_docs_closed(settings: Settings) -> Iterator[GateViolation]:
    """API docs reveal the whole admin and billing schema."""
    if settings.web.api_docs_enabled:
        yield GateViolation("API_DOCS_ENABLED", "документация API в production выключена")


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
        yield GateViolation("LOG_LEVEL", "DEBUG для всего процесса в production запрещён")


def storage_over_tls(settings: Settings) -> Iterator[GateViolation]:
    """Files and their signed links travel to each home's bucket only over TLS."""
    for home, home_settings in settings.homes.items():
        if home_settings.s3_endpoint_url.scheme != SECURE_STORAGE_SCHEME:
            yield GateViolation(
                f"{home_prefix(home)}S3_ENDPOINT_URL", "к хранилищу в production — только https"
            )


CORE_CHECKS: tuple[ProductionCheck, ...] = (
    api_docs_closed,
    proxies_trusted,
    encryption_key_present,
    debug_logs_off,
    storage_over_tls,
)
