"""Identity's settings (`IDENTITY_*`) and the production checks of its secrets (ADR 0045).

The values are documented in `.env.example` section 2. Development values start with
`dev`, and the gate refuses them in staging and production.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, Final

from pydantic import AfterValidator, BeforeValidator, Field, SecretStr
from pydantic_settings import NoDecode

from shosai.core.config.gate import GateViolation
from shosai.core.config.loading import Settings
from shosai.core.config.sections import SettingsSection
from shosai.core.config.values import split_commas
from shosai.features.identity.domain.directory import DIRECTORY_KEY_MIN_BYTES

KEY_ID: Final = re.compile(r"[a-z0-9-]{1,16}")
# Ключ черновика (jwt_secret, DATA_MAPPING R6): им подписаны токены без kid.
DRAFT_KEY_ID: Final = "d"
DEVELOPMENT_MARK: Final = "dev"
PRODUCTION_HASH_ROUNDS: Final = 12
# Ключи подписи HS256 — не короче 256 бит (RFC 7518 §3.2), ключ черновика тоже.
MIN_KEY_BYTES: Final = 32


@dataclass(frozen=True, slots=True)
class TokenKey:
    """One signing key of the ring and its id, sent as the `kid` header."""

    key_id: str
    secret: SecretStr


def check_token_keys(entries: tuple[SecretStr, ...]) -> tuple[SecretStr, ...]:
    """Each entry is `kid:secret`; ids are unique; the ring is not empty."""
    if not entries:
        message = "нужен хотя бы один ключ подписи"
        raise ValueError(message)
    keys = [_split_entry(entry) for entry in entries]
    if any(len(key.secret.get_secret_value().encode("utf-8")) < MIN_KEY_BYTES for key in keys):
        message = f"каждый ключ подписи — не короче {MIN_KEY_BYTES} байт (RFC 7518 §3.2)"
        raise ValueError(message)
    ids = [key.key_id for key in keys]
    if len(ids) != len(set(ids)):
        message = "id ключей подписи повторяются"
        raise ValueError(message)
    return entries


def check_directory_key(key: SecretStr) -> SecretStr:
    """The directory key is at least 32 bytes."""
    if len(key.get_secret_value().encode("utf-8")) < DIRECTORY_KEY_MIN_BYTES:
        message = f"ключ каталога — не короче {DIRECTORY_KEY_MIN_BYTES} байт"
        raise ValueError(message)
    return key


TokenKeyEntries = Annotated[
    tuple[SecretStr, ...],
    NoDecode,
    BeforeValidator(split_commas),
    AfterValidator(check_token_keys),
]


class IdentitySettings(SettingsSection):
    """Signing keys, the directory key and the cost of password hashing."""

    # Кольцо ключей подписи «kid:секрет» через запятую: первый подписывает, остальные только
    # проверяют. Ключ черновика — под id «d»: им подписаны токены без заголовка kid.
    identity_token_keys: TokenKeyEntries
    # HMAC адреса в каталоге (§6, §15): живёт вне базы, без него каталог не прочитать.
    identity_directory_hmac_key: Annotated[SecretStr, AfterValidator(check_directory_key)]
    # Стоимость bcrypt: 12 вне разработки (≈ 250 мс), в тестах меньше ради скорости.
    identity_password_hash_rounds: int = Field(default=PRODUCTION_HASH_ROUNDS, ge=4, le=15)
    # Cloudflare Turnstile (ADR 0045 п. 4): ключ сайта — в кабинет, секрет — только серверу.
    # Без секрета капча выключена; вне разработки секрет обязателен.
    identity_turnstile_site_key: str | None = None
    identity_turnstile_secret_key: SecretStr | None = None
    # Вход через соцсети (ID-D8): провайдер включён, когда задан его client id (у VK ID —
    # без секрета, обмен кода идёт по PKCE). Адрес возврата — {PUBLIC_BASE_URL}/v1/auth/social/
    # {провайдер}/callback, у Яндекса ещё …/yandex/token-page для виджета.
    identity_yandex_client_id: str | None = None
    identity_yandex_client_secret: SecretStr | None = None
    identity_vk_client_id: str | None = None
    identity_google_client_id: str | None = None
    identity_google_client_secret: SecretStr | None = None
    identity_github_client_id: str | None = None
    identity_github_client_secret: SecretStr | None = None
    # Cookie сессии: Secure вне локальной разработки по HTTP; домен — пусто, cookie хоста.
    identity_cookie_secure: bool = True
    identity_cookie_domain: str | None = None

    def token_keys(self) -> tuple[TokenKey, ...]:
        """The signing ring in order: the first key signs, every key verifies."""
        return tuple(_split_entry(entry) for entry in self.identity_token_keys)


def identity_secrets_safe(settings: Settings) -> Iterator[GateViolation]:
    """No development key and no cheap hashing outside development."""
    identity = settings.features.get(IdentitySettings)
    for key in identity.token_keys():
        if key.key_id.startswith(DEVELOPMENT_MARK):
            yield GateViolation("IDENTITY_TOKEN_KEYS", f"ключ разработки {key.key_id} вне неё")
    if identity.identity_directory_hmac_key.get_secret_value().startswith(DEVELOPMENT_MARK):
        yield GateViolation("IDENTITY_DIRECTORY_HMAC_KEY", "ключ каталога разработки вне неё")
    if identity.identity_turnstile_secret_key is None or not identity.identity_turnstile_site_key:
        yield GateViolation(
            "IDENTITY_TURNSTILE_SECRET_KEY", "без Turnstile регистрация не защищена"
        )
    if not identity.identity_cookie_secure:
        yield GateViolation(
            "IDENTITY_COOKIE_SECURE", "cookie сессии вне разработки — только Secure"
        )
    if identity.identity_password_hash_rounds < PRODUCTION_HASH_ROUNDS:
        yield GateViolation(
            "IDENTITY_PASSWORD_HASH_ROUNDS",
            f"вне разработки стоимость bcrypt — не ниже {PRODUCTION_HASH_ROUNDS}",
        )


def _split_entry(entry: SecretStr) -> TokenKey:
    key_id, separator, secret = entry.get_secret_value().partition(":")
    if not separator or not KEY_ID.fullmatch(key_id) or not secret:
        message = "ключ подписи — «kid:секрет», kid из строчных латинских букв, цифр и дефиса"
        raise ValueError(message)
    return TokenKey(key_id, SecretStr(secret))
