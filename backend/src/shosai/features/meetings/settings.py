"""The meetings slice's settings (`LIVEKIT_*`, `MEETINGS_*`) and their production check.

Calls run on LiveKit: clients connect to its public signalling address, the API talks to its
server API on the plane's network, and both sign with one key and secret. All four are set
together or not at all; without them the app starts and every call route answers 503
`video_unavailable`. Outside development the public address is TLS and the secret is long
enough to sign tokens safely.
"""

from collections.abc import Iterator
from typing import Final

from pydantic import AnyUrl, Field, HttpUrl, SecretStr, UrlConstraints

from shosai.core.config.gate import GateViolation
from shosai.core.config.loading import Settings
from shosai.core.config.sections import SettingsSection

# LiveKit не примет ключ HS256 короче 32 символов: подпись была бы подбираемой.
MIN_SECRET_LENGTH: Final = 32
SECURE_SIGNAL_SCHEME: Final = "wss"


class SignalUrl(AnyUrl):
    """A WebSocket address of LiveKit's signalling."""

    _constraints = UrlConstraints(allowed_schemes=["ws", "wss"], host_required=True)


class LiveKitSettings(SettingsSection):
    """Where LiveKit is and how the API signs for it."""

    # Адрес сигнализации для клиентов: wss://rtc.shosai.tech; в разработке ws://127.0.0.1:17880.
    livekit_url: SignalUrl | None = None
    # Серверный API внутри плоскости, без префикса пути: http://livekit:7880.
    livekit_api_url: HttpUrl | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: SecretStr | None = None

    @property
    def configured(self) -> bool:
        """Whether every LiveKit setting is set."""
        return None not in (
            self.livekit_url,
            self.livekit_api_url,
            self.livekit_api_key,
            self.livekit_api_secret,
        )


class MeetingsSettings(SettingsSection):
    """The platform's bounds on calls."""

    # Потолок участников звонка над значением тарифа (MR-D2): 50, на стейджинге 4.
    meetings_room_participants_ceiling: int = Field(default=50, ge=2, le=1_000)
    # Видеозаписей одновременно на всю платформу и длина одной (MR-D14: на стейджинге 1 и 30 мин).
    meetings_recordings_concurrent: int = Field(default=1, ge=1, le=100)
    meetings_recording_max_minutes: int = Field(default=30, ge=1, le=600)
    # Адрес бакета дома, каким его видит egress, если он не тот, что у API (в разработке —
    # имя сервиса в сети Compose); пусто — адрес дома.
    meetings_egress_s3_endpoint_ru: str | None = None
    meetings_egress_s3_endpoint_eu: str | None = None
    # Prometheus стека наблюдаемости: история и узлы LiveKit на экране администратора (A8).
    meetings_prometheus_url: HttpUrl = HttpUrl("http://prometheus:9090")
    # Предел памяти контейнера LiveKit, как его задаёт выкладка; доля памяти узла считается от
    # него, а без него экран показывает «нет данных».
    meetings_livekit_memory_limit_mb: int | None = Field(default=None, ge=64, le=1_048_576)


def livekit_settings_safe(settings: Settings) -> Iterator[GateViolation]:
    """LiveKit is set as a whole, over TLS for clients, with a secret long enough to sign."""
    livekit = settings.features.get(LiveKitSettings)
    given = {
        "LIVEKIT_URL": livekit.livekit_url,
        "LIVEKIT_API_URL": livekit.livekit_api_url,
        "LIVEKIT_API_KEY": livekit.livekit_api_key,
        "LIVEKIT_API_SECRET": livekit.livekit_api_secret,
    }
    missing = [name for name, value in given.items() if value is None]
    if missing and len(missing) < len(given):
        for name in missing:
            yield GateViolation(name, "LiveKit задаётся целиком: без этой настройки звонки не идут")
        return
    if livekit.livekit_url is not None and livekit.livekit_url.scheme != SECURE_SIGNAL_SCHEME:
        yield GateViolation("LIVEKIT_URL", "клиенты подключаются к LiveKit только по wss://")
    secret = livekit.livekit_api_secret
    if secret is not None and len(secret.get_secret_value()) < MIN_SECRET_LENGTH:
        yield GateViolation("LIVEKIT_API_SECRET", "секрет LiveKit — не короче 32 символов")
