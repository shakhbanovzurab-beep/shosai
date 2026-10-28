"""A provider's descriptor: everything the core needs to know about it, as data (plan §3.2).

The authorize and token endpoints, how the client proves itself at the token endpoint,
PKCE, the scope separator and the extra authorize parameters, whether refresh tokens rotate
and how long an unused one lives, how a grant is revoked, the limits to keep and the
timeouts. A provider is a descriptor and its adapters; the core reads only this, so adding
a provider changes nothing in it. Each provider's descriptor arrives with its step and is
checked against the provider's recorded answers there.
"""

import re
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Final
from urllib.parse import urlsplit

from shosai.features.connectors.domain.catalogue import Provider

MAX_CALL_TIMEOUT: Final = timedelta(seconds=60)
AUTH_SCHEMES: Final = frozenset({"Bearer", "OAuth"})
REDIRECT_PATH: Final = re.compile(r"/v1(/[a-z0-9_]+)+")


class TokenAuth(StrEnum):
    """How the client authenticates at the token endpoint."""

    # client_id и client_secret в теле формы (RFC 6749 §2.3.1, второй способ).
    BODY = "body"
    # HTTP Basic с client_id и client_secret (RFC 6749 §2.3.1, первый способ).
    BASIC = "basic"
    # Тело JSON вместо формы (Atlassian).
    JSON = "json"
    # Basic и тело JSON (Notion).
    BASIC_JSON = "basic_json"


class RevocationKind(StrEnum):
    """What a disconnect sends to the provider, if anything."""

    # Отзыв по refresh-токену (Google: снимает весь проект).
    REFRESH = "refresh"
    # Отзыв по токену доступа или любому из пары.
    ACCESS = "access"
    # Удаление гранта приложения целиком (GitHub).
    GRANT = "grant"
    # У провайдера нет отзыва для приложения: Shosai только забывает.
    NONE = "none"


class LimitSubject(StrEnum):
    """What a provider's quota counts."""

    APPLICATION = "application"
    ACCOUNT = "account"
    CONNECTION = "connection"


@dataclass(frozen=True, slots=True)
class ProviderLimit:
    """One quota: `requests` per `period` per subject, with a burst allowance."""

    name: str
    subject: LimitSubject
    requests: int
    period: timedelta
    burst: int = 1

    def __post_init__(self) -> None:
        if self.requests < 1 or self.burst < 1 or self.period <= timedelta(0):
            message = f"лимит {self.name}: запросы, всплеск и период — положительные"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class Revocation:
    """How a grant is revoked at the provider."""

    kind: RevocationKind
    url: str | None = None

    def __post_init__(self) -> None:
        if (self.kind is RevocationKind.NONE) != (self.url is None):
            message = "адрес отзыва есть тогда и только тогда, когда отзыв есть"
            raise ValueError(message)
        if self.url is not None:
            check_https(self.url)


@dataclass(frozen=True, slots=True)
class Timeouts:
    """Deadlines of calls to the provider (plan §3.6)."""

    connect: timedelta = timedelta(seconds=3)
    read: timedelta = timedelta(seconds=15)
    token: timedelta = timedelta(seconds=10)

    def __post_init__(self) -> None:
        for value in (self.connect, self.read, self.token):
            if not timedelta(0) < value <= MAX_CALL_TIMEOUT:
                message = "срок вызова провайдера — от нуля до минуты"
                raise ValueError(message)


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """One OAuth application's provider, as the core sees it."""

    provider: Provider
    # Ключ приложения OAuth: google, google_mail, github_app; из него — переменные окружения.
    client_key: str
    authorize_url: str
    token_url: str
    token_auth: TokenAuth
    pkce: bool
    revocation: Revocation
    scope_separator: str = " "
    authorize_params: tuple[tuple[str, str], ...] = ()
    # Новый refresh-токен на каждое обновление, старый становится недействительным.
    rotating_refresh: bool = False
    # Через сколько неиспользуемый refresh-токен умирает; None — живёт, пока не отозван.
    idle_expiry: timedelta | None = None
    # Один токен на аккаунт со всеми правами: вход просит объединение прав (Яндекс, Atlassian).
    union_scopes: bool = False
    limits: tuple[ProviderLimit, ...] = ()
    # Сколько вызовов одного аккаунта одновременно (Outlook: 4 на ящик); None — без предела.
    concurrency_per_account: int | None = None
    timeouts: Timeouts = field(default_factory=Timeouts)
    # Схема заголовка Authorization: Bearer, у Яндекса — OAuth.
    auth_scheme: str = "Bearer"
    # Свой путь обратного адреса, если его зарегистрировало приложение (Atlassian — путь черновика).
    redirect_path: str | None = None

    def __post_init__(self) -> None:
        check_https(self.authorize_url)
        check_https(self.token_url)
        if not self.scope_separator or self.scope_separator.strip(" ,"):
            message = f"{self.client_key}: разделитель прав — пробел или запятая"
            raise ValueError(message)
        reserved = {"client_id", "redirect_uri", "state", "code_challenge", "scope"}
        if reserved & {name for name, _ in self.authorize_params}:
            message = f"{self.client_key}: дополнительные параметры не задают служебные поля"
            raise ValueError(message)
        if self.concurrency_per_account is not None and self.concurrency_per_account < 1:
            message = f"{self.client_key}: предел одновременных вызовов — положительный"
            raise ValueError(message)
        if self.auth_scheme not in AUTH_SCHEMES:
            message = f"{self.client_key}: схема авторизации — {', '.join(sorted(AUTH_SCHEMES))}"
            raise ValueError(message)
        if self.redirect_path is not None and not REDIRECT_PATH.fullmatch(self.redirect_path):
            message = f"{self.client_key}: обратный путь — /v1/… из букв, цифр, / и _"
            raise ValueError(message)
        names = [limit.name for limit in self.limits]
        if len(names) != len(set(names)):
            message = f"{self.client_key}: лимит назван дважды"
            raise ValueError(message)


def check_https(url: str) -> None:
    """Refuse a provider address that is not plain HTTPS with a host."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        message = f"адрес провайдера {url!r} — HTTPS с хостом и без учётных данных"
        raise ValueError(message)
