"""Who pays for a model call, why it is made and which model it goes to (F6 plan §3.3).

Every call carries a `CallContext`: the account and company it is made for — or a platform
account when no user stands behind it — its effect key, its feature, its class and origin.
The effect key names the effect, not the request: a retried request, a redelivered task or
a repeated pipeline stage pass the same key, and the call is then recorded once (inv-9).
Value types only: no framework, driver or client (ADR 0034 point 4).
"""

import re
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope

FEATURE_NAME: Final = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*")
EFFECT_KEY_MAX_LENGTH: Final = 200


class CallClass(StrEnum):
    """What money may do to a call (F6-C4, inv-13)."""

    # Встреча, обычная расшифровка и разметка спикеров: учитываются, деньгами не останавливаются.
    ESSENTIAL = "essential"
    STANDARD = "standard"
    # Премиальные модели, голос, перевод, картинки: при сбое Valkey закрываются первыми.
    EXPENSIVE = "expensive"


class CallOrigin(StrEnum):
    """Who started the call: the person now, the platform on their behalf, or the platform."""

    INTERACTIVE = "interactive"
    BACKGROUND = "background"
    SYSTEM = "system"


class PlatformAccount(StrEnum):
    """Who pays for a call without a user (F6-C19); platform calls are recorded in the EU home."""

    LANDING_DEMO = "landing_demo"
    HELP_ASSISTANT = "help_assistant"
    SYSTEM = "system"


class Provider(StrEnum):
    """The AI providers the port reaches (§18.2)."""

    # Чат, картинки, эмбеддинги и расшифровка записей; разметку говорящих делает pyannote.
    OPENROUTER = "openrouter"
    PYANNOTE = "pyannote"
    # Потоковая расшифровка живой встречи моделями Realtime (ADR 0043).
    OPENAI = "openai"
    # Gemini Live: синхронный перевод и голосовой ассистент.
    GOOGLE = "google"
    # Распознавание сканов и картинок документов (OCR).
    MISTRAL = "mistral"


@dataclass(frozen=True, slots=True)
class ModelRef:
    """One model of one provider, as the provider names it."""

    provider: Provider
    model: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.model) <= 128:
            message = "имя модели — от 1 до 128 символов"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class ModelRoute:
    """The model a caller chose and its same-tier fallbacks, in order (§11.1 of the Leo design)."""

    primary: ModelRef
    fallbacks: tuple[ModelRef, ...] = ()

    @property
    def models(self) -> tuple[ModelRef, ...]:
        """The models in the order they are tried."""
        return (self.primary, *self.fallbacks)


@dataclass(frozen=True, slots=True)
class CallContext:
    """Who the call is for, how it is keyed and labelled, and what limits it carries."""

    effect_key: str
    feature: str
    call_class: CallClass
    origin: CallOrigin
    scope: TenancyScope | None = None
    platform_account: PlatformAccount | None = None
    # Согласие на передачу данных за границу: без него вызов из дома RU не уходит (nfr-14).
    cross_border_consent: bool = False
    deadline: timedelta | None = None

    def __post_init__(self) -> None:
        if not 1 <= len(self.effect_key) <= EFFECT_KEY_MAX_LENGTH:
            message = f"ключ эффекта вызова — от 1 до {EFFECT_KEY_MAX_LENGTH} символов"
            raise ValueError(message)
        if len(self.feature) > 48 or not FEATURE_NAME.fullmatch(self.feature):
            message = "функция вызова — имя в snake_case через точку, до 48 символов"
            raise ValueError(message)
        if (self.scope is None) == (self.platform_account is None):
            message = "вызов оплачивает либо пользователь (scope), либо платформенный аккаунт"
            raise ValueError(message)
        if self.scope is not None and self.scope.user_id is None:
            message = "вызов за пользователя называет его user_id"
            raise ValueError(message)
        if self.deadline is not None and self.deadline <= timedelta(0):
            message = "срок вызова больше нуля"
            raise ValueError(message)

    @property
    def payer_scope(self) -> TenancyScope:
        """The scope the cost row is written in: the user's, or the EU home for the platform."""
        return self.scope if self.scope is not None else TenancyScope(Home.EU)
