"""Value types of the settings: environment, log level, URLs, origins, proxies, keys.

A validation message names the problem and never the value: a value may hold a password.
Lists come from one comma-separated variable, never from JSON.
"""

import base64
import binascii
from enum import StrEnum
from ipaddress import IPv4Network, IPv6Network, ip_network
from typing import Annotated
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BeforeValidator, Field, SecretStr
from pydantic_settings import NoDecode

# Стандартный адрес libpq: драйвер выбирает код (ADR 0013), а psql и другие инструменты
# принимают ту же строку.
DATABASE_URL_SCHEME = "postgresql"
# В строке запроса адреса базы — только параметры TLS; соединение (таймауты, имя
# приложения, подготовленные выражения) настраивает код, и адрес не может их перебить.
DATABASE_URL_TLS_PARAMETERS = frozenset(
    {"sslmode", "sslrootcert", "sslcert", "sslkey", "sslcrl", "sslcrldir", "sslnegotiation"}
)
REDIS_URL_SCHEMES = frozenset({"redis", "rediss"})
ORIGIN_SCHEMES = frozenset({"http", "https"})
FERNET_KEY_BYTES = 32


class Environment(StrEnum):
    """Where the process runs; every environment but development is behind the safety gate."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_gated(self) -> bool:
        """Staging is reachable from the internet with real-shaped data, so it is gated too."""
        return self is not Environment.DEVELOPMENT


class LogLevel(StrEnum):
    """Lowest level of log lines a process writes."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


def split_commas(value: object) -> object:
    """`a, b,,c` → `["a", "b", "c"]`; a value that is not a string is left to validation."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def upper_case(value: object) -> object:
    """Log levels are accepted in any case: `info` and `INFO` mean the same."""
    return value.upper() if isinstance(value, str) else value


def check_database_url(url: SecretStr) -> SecretStr:
    """A libpq PostgreSQL address with a host, a database name and only TLS parameters."""
    parts = urlsplit(url.get_secret_value())
    if parts.scheme != DATABASE_URL_SCHEME:
        message = f"ожидается адрес вида {DATABASE_URL_SCHEME}://…"
        raise ValueError(message)
    if not parts.hostname or not parts.path.removeprefix("/"):
        message = "в адресе нужны хост и имя базы"
        raise ValueError(message)
    if parts.fragment or any(
        name not in DATABASE_URL_TLS_PARAMETERS
        for name, _ in parse_qsl(parts.query, keep_blank_values=True)
    ):
        allowed = ", ".join(sorted(DATABASE_URL_TLS_PARAMETERS))
        message = f"в строке запроса допустимы только параметры TLS: {allowed}"
        raise ValueError(message)
    return url


def database_url_parameter(url: SecretStr, name: str) -> str | None:
    """The value of one query parameter of a database address, if it is given."""
    query = parse_qsl(urlsplit(url.get_secret_value()).query, keep_blank_values=True)
    return next((value for key, value in query if key == name), None)


def check_redis_url(url: SecretStr) -> SecretStr:
    """A Redis-protocol address (Valkey or the Redis cache) with a host."""
    parts = urlsplit(url.get_secret_value())
    if parts.scheme not in REDIS_URL_SCHEMES or not parts.hostname:
        message = "ожидается адрес вида redis://… или rediss://… с хостом"
        raise ValueError(message)
    return url


def normalize_origin(value: str) -> str:
    """An exact browser origin `scheme://host[:port]`; a wildcard is never an origin."""
    message = "ожидается точный origin вида https://host[:port], «*» не допускается"
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError:
        raise ValueError(message) from None
    if (
        parts.scheme not in ORIGIN_SCHEMES
        or not parts.hostname
        or parts.username is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise ValueError(message)
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    return f"{parts.scheme}://{host}" + (f":{port}" if port is not None else "")


def parse_proxy_network(value: object) -> object:
    """An IP address or a CIDR network of a trusted reverse proxy."""
    if not isinstance(value, str):
        return value
    try:
        return ip_network(value, strict=False)
    except ValueError:
        message = "ожидается IP-адрес или сеть CIDR, «*» не допускается"
        raise ValueError(message) from None


def check_fernet_key(key: SecretStr) -> SecretStr:
    """A Fernet key: 32 bytes in URL-safe base64, as `Fernet.generate_key()` makes it."""
    try:
        raw = base64.b64decode(key.get_secret_value(), altchars=b"-_", validate=True)
    except binascii.Error:
        raw = b""
    if len(raw) != FERNET_KEY_BYTES:
        message = "ключ Fernet — 32 байта в URL-safe base64"
        raise ValueError(message)
    return key


def check_time_zone(name: str) -> str:
    """An IANA time zone the server's tzdata knows, such as `Europe/Moscow`."""
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        message = "ожидается часовой пояс IANA, например Europe/Moscow"
        raise ValueError(message) from error
    return name


# Обычные псевдонимы, а не `type`: pydantic-settings ищет NoDecode в метаданных поля,
# а псевдоним `type` прячет их внутри своей схемы.
DatabaseUrl = Annotated[SecretStr, AfterValidator(check_database_url)]
RedisUrl = Annotated[SecretStr, AfterValidator(check_redis_url)]
NonEmptyText = Annotated[str, Field(min_length=1)]
Port = Annotated[int, Field(ge=1, le=65535)]
Origin = Annotated[str, AfterValidator(normalize_origin)]
ProxyNetwork = Annotated[IPv4Network | IPv6Network, BeforeValidator(parse_proxy_network)]
FernetKey = Annotated[SecretStr, AfterValidator(check_fernet_key)]
LogLevelName = Annotated[LogLevel, BeforeValidator(upper_case)]
Origins = Annotated[tuple[Origin, ...], NoDecode, BeforeValidator(split_commas)]
ProxyNetworks = Annotated[tuple[ProxyNetwork, ...], NoDecode, BeforeValidator(split_commas)]
FernetKeys = Annotated[tuple[FernetKey, ...], NoDecode, BeforeValidator(split_commas)]
TimeZoneName = Annotated[str, AfterValidator(check_time_zone)]
