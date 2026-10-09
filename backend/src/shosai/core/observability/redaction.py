"""Redaction of secrets in log events (CLAUDE.md "Security", target architecture §16.8).

Three rules, applied at any depth of the event: a value under a sensitive key is replaced;
a `SecretStr` or `SecretBytes` anywhere is replaced; the password inside a URL such as
`postgresql://user:password@host` is replaced in any string, the message included.
"""

import re
from collections.abc import Mapping
from typing import Any

from pydantic import SecretBytes, SecretStr
from structlog.typing import EventDict, WrappedLogger

REDACTED = "***"
MAX_DEPTH = 8
TRUNCATED = "<слишком глубоко>"

# Точный список, а не подстрока: правило «*token*» стёрло бы input_tokens и output_tokens —
# счётчики расхода моделей, которые нужны в логах.
SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "bearer",
        "client_secret",
        "cookie",
        "credential",
        "credentials",
        "dsn",
        "fernet_key",
        "fernet_keys_previous",
        "jwt",
        "passphrase",
        "passwd",
        "password",
        "private_key",
        "proxy_authorization",
        "refresh_token",
        "secret",
        "secret_access_key",
        "set_cookie",
        "token",
    }
)
# Множественное «_tokens» под правило не подпадает: это счётчики, а не токены.
SENSITIVE_SUFFIXES = ("_secret", "_password", "_api_key", "_token", "_secret_access_key")
# Пароль — всё от двоеточия после имени до «@»: в нём может оказаться и незакодированный «/».
URL_PASSWORD = re.compile(r"(?P<head>[a-z][a-z0-9+.-]*://[^\s:/@]*:)[^\s@]*@", re.IGNORECASE)


def is_sensitive_key(key: str) -> bool:
    """A key whose value is never logged: `Password`, `X-Api-Key`, `refresh_token`…."""
    normalized = key.lower().replace("-", "_")
    return normalized in SENSITIVE_KEYS or normalized.endswith(SENSITIVE_SUFFIXES)


def redact_value(value: object, depth: int = 0) -> object:
    """The value with every secret it contains replaced; containers are copied, not changed."""
    if depth > MAX_DEPTH:
        return TRUNCATED
    match value:
        case SecretStr() | SecretBytes():
            return REDACTED
        case str():
            return URL_PASSWORD.sub(rf"\g<head>{REDACTED}@", value)
        case Mapping():
            return {
                key: REDACTED if is_sensitive_key(str(key)) else redact_value(item, depth + 1)
                for key, item in value.items()
            }
        case list() | tuple() | set() | frozenset():
            return [redact_value(item, depth + 1) for item in value]
        case _:
            return value


def redact_event(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    """structlog processor: the event with secrets replaced, ready for rendering."""
    redacted: dict[str, Any] = {
        key: REDACTED if is_sensitive_key(key) else redact_value(value)
        for key, value in event_dict.items()
    }
    return redacted
