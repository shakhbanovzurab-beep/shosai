"""Connectors' invariant monitors (plan §3.11): zero is the only healthy value.

A secret no key opens means a grant Shosai can no longer use and the person was not told; a
rotated refresh token lost between the provider's answer and the commit means one grant
broke without the person's doing; a refusal of Shosai's own application means every grant of
it stops at its next refresh — an expired client secret, most often.
"""

from typing import Final

from shosai.core.observability.objectives import InvariantMonitor, NeverIncreases, StaysAtMost
from shosai.features.connectors.infrastructure.metrics import (
    CLIENT_MISCONFIGURED,
    REFRESH_LOST,
    UNDECRYPTABLE,
)

MONITORS: Final = (
    InvariantMonitor(
        name="connector_secret_undecryptable",
        invariant="ADR 0075",
        summary="Секрет подключения не расшифровывается",
        explanation=(
            "Еженедельная проверка нашла токены или пароли подключённых сервисов, которые не "
            "открывает ни один ключ кольца Fernet. Эти подключения больше не работают, а человек "
            "об этом не знает. Обычно это значит, что ключ убрали из FERNET_KEYS_PREVIOUS "
            "раньше, чем закончилась ротация."
        ),
        condition=StaysAtMost(UNDECRYPTABLE, 0),
    ),
    InvariantMonitor(
        name="connector_refresh_lost",
        invariant="ADR 0075",
        summary="Новый токен подключения потерян",
        explanation=(
            "Провайдер выдал новый refresh-токен, а записать его в базу не удалось. У таких "
            "провайдеров старый токен уже не работает, поэтому подключение сломается при "
            "следующем вызове, и человеку придётся подключить сервис заново."
        ),
        condition=NeverIncreases(REFRESH_LOST),
    ),
    InvariantMonitor(
        name="connector_client_misconfigured",
        invariant="ADR 0075",
        summary="Провайдер отверг приложение Shosai",
        explanation=(
            "Провайдер ответил, что не знает приложение OAuth Shosai или его секрет. Каждое "
            "подключение к этому провайдеру перестанет работать при следующем обновлении "
            "токена. Чаще всего истёк секрет приложения, например в Microsoft Entra."
        ),
        condition=NeverIncreases(CLIENT_MISCONFIGURED),
    ),
)
