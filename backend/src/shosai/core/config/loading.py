"""Reading the settings of a process from an explicit mapping of environment variables.

The entry point passes `os.environ`; tests pass their own mapping. Every problem is
collected and reported at once by variable name; a value never enters a message, and the
original `ValidationError` (whose text contains the input) is never chained.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import ValidationError
from pydantic_settings import BaseSettings, EnvSettingsSource, SettingsError

from shosai.core.config.sections import (
    AiGuardSettings,
    AiSettings,
    CryptoSettings,
    EmailSettings,
    ExchangeRateSettings,
    HomeSettings,
    ObservabilitySettings,
    RuntimeSettings,
    ServerSettings,
    SharedServicesSettings,
    SpendSettings,
    StorageSettings,
    WebSettings,
    home_prefix,
)
from shosai.core.config.values import Environment
from shosai.core.kernel.homes import Home

MISSING_ERROR_TYPE = "missing"


class ConfigurationError(Exception):
    """The environment does not describe a valid process; the message names the variables."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("Настройки процесса отклонены:\n" + "\n".join(problems))


class EnvironSource(EnvSettingsSource):
    """The environment-variable source of pydantic-settings over a given mapping."""

    def __init__(
        self, settings_cls: type[BaseSettings], environ: Mapping[str, str], env_prefix: str
    ) -> None:
        self._environ = environ
        super().__init__(settings_cls, env_prefix=env_prefix)

    def _load_env_vars(self) -> Mapping[str, str | None]:
        # Тот же разбор, что у базового источника, только над переданным отображением.
        return {
            (name if self.case_sensitive else name.lower()): value
            for name, value in self._environ.items()
            if not (self.env_ignore_empty and value == "")
        }


@dataclass(frozen=True, slots=True)
class Settings:
    """Settings of one process: built once at start, then passed to whoever needs them."""

    environment: Environment
    homes: Mapping[Home, HomeSettings]
    storage: StorageSettings
    shared_services: SharedServicesSettings
    web: WebSettings
    server: ServerSettings
    observability: ObservabilitySettings
    crypto: CryptoSettings
    ai: AiSettings
    spend: SpendSettings
    ai_guards: AiGuardSettings
    email: EmailSettings
    exchange_rates: ExchangeRateSettings


def load_settings(environ: Mapping[str, str]) -> Settings:
    """Build the settings from environment variables or raise `ConfigurationError`."""
    reader = _SectionReader(environ)
    runtime = reader.read(RuntimeSettings, "")
    homes = {home: reader.read(HomeSettings, home_prefix(home)) for home in Home}
    storage = reader.read(StorageSettings, "")
    shared_services = reader.read(SharedServicesSettings, "")
    web = reader.read(WebSettings, "")
    server = reader.read(ServerSettings, "")
    observability = reader.read(ObservabilitySettings, "")
    crypto = reader.read(CryptoSettings, "")
    ai = reader.read(AiSettings, "")
    spend = reader.read(SpendSettings, "")
    ai_guards = reader.read(AiGuardSettings, "")
    email = reader.read(EmailSettings, "")
    exchange_rates = reader.read(ExchangeRateSettings, "")
    if reader.problems:
        raise ConfigurationError(reader.problems)
    return Settings(
        environment=_present(runtime).environment,
        homes=MappingProxyType({home: _present(section) for home, section in homes.items()}),
        storage=_present(storage),
        shared_services=_present(shared_services),
        web=_present(web),
        server=_present(server),
        observability=_present(observability),
        crypto=_present(crypto),
        ai=_present(ai),
        spend=_present(spend),
        ai_guards=_present(ai_guards),
        email=_present(email),
        exchange_rates=_present(exchange_rates),
    )


class _SectionReader:
    """Reads sections one by one and collects every problem instead of stopping at the first."""

    def __init__(self, environ: Mapping[str, str]) -> None:
        self._environ = environ
        self.problems: list[str] = []

    def read[S: BaseSettings](self, section: type[S], prefix: str) -> S | None:
        """The section validated from the variables with the prefix, or None and its problems."""
        try:
            values = EnvironSource(section, self._environ, env_prefix=prefix)()
            return section.model_validate(values)
        except SettingsError as error:
            # Значение-JSON не разобрано; сообщение pydantic-settings называет поле, но не значение.
            self.problems.append(f"{section.__name__}: {error}")
        except ValidationError as error:
            self.problems.extend(_describe(error, prefix, section.__name__))
        return None


def _present[S](section: S | None) -> S:
    # Секция без проблем всегда прочитана; проверка лишь сужает тип и не даёт пройти дальше
    # при ошибке в самом загрузчике.
    if section is None:
        message = "секция настроек не прочитана, а проблем не записано"
        raise ConfigurationError([message])
    return section


def _describe(error: ValidationError, prefix: str, section: str) -> list[str]:
    problems: list[str] = []
    for item in error.errors(include_url=False, include_input=False, include_context=False):
        field = str(item["loc"][0]) if item["loc"] else ""
        # Проверка всей секции (например, разные порты) не привязана к одной переменной.
        variable = f"{prefix}{field}".upper() if field else section
        if item["type"] == MISSING_ERROR_TYPE:
            problems.append(f"{variable}: обязательная переменная не задана")
        else:
            problems.append(f"{variable}: {item['msg']}")
    return problems
