"""Social sign-in rules: which providers a visitor sees, the signed state, safe returns.

Yandex and VK serve Russia and unknown countries, Google and GitHub everyone else, and
the two sets are never shown together (406-FZ; ID-D8). The country comes from the edge,
never from the client; a Russian interface also shows the Russian set. A provider's email
links to an existing account only when that provider proves it verified the address; VK ID
is not trusted for that (ADR 0045 point 10).
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from shosai.features.identity.domain.homes import RUSSIA

STATE_SEPARATOR: Final = "-"  # VK вырезает точки из state (урок черновика).
NONCE_BYTES: Final = 16
MAX_NEXT_LENGTH: Final = 256


class Provider(StrEnum):
    """The social sign-in providers."""

    YANDEX = "yandex"
    VK = "vk"
    GOOGLE = "google"
    GITHUB = "github"


RUSSIAN_SET: Final = (Provider.YANDEX, Provider.VK)
WORLD_SET: Final = (Provider.GOOGLE, Provider.GITHUB)


@dataclass(frozen=True, slots=True)
class SocialIdentity:
    """Who the provider says the person is; its tokens are never kept."""

    provider: Provider
    subject: str
    email: str | None
    email_verified: bool
    display_name: str | None


def visible_providers(country: str | None, language: str | None) -> tuple[Provider, ...]:
    """The set a visitor sees: Russian for Russia or a Russian interface, the world's otherwise.

    A country the edge did not name decides nothing here: the interface language does (owner's
    decision of 2026-10-15). The home of a first mail keeps its own, stricter rule (`homes`).
    """
    russian = (country or "").upper() == RUSSIA or (language or "").lower().startswith("ru")
    return RUSSIAN_SET if russian else WORLD_SET


def sign_state(key: bytes) -> tuple[str, str]:
    """A new nonce and the state that carries it: `nonce-HMAC(nonce)`."""
    nonce = secrets.token_hex(NONCE_BYTES)
    return nonce, f"{nonce}{STATE_SEPARATOR}{_mac(key, nonce)}"


def state_nonce(key: bytes, state: str) -> str | None:
    """The nonce of a state this server signed, or None."""
    nonce, separator, mac = state.partition(STATE_SEPARATOR)
    if not separator or not nonce or not secrets.compare_digest(mac, _mac(key, nonce)):
        return None
    return nonce


def safe_next(path: str | None) -> str:
    """A return path inside the cabinet, or the empty path (an open-redirect guard)."""
    if not path or len(path) > MAX_NEXT_LENGTH:
        return ""
    if not path.startswith("/app") or path.startswith("//") or "\\" in path:
        return ""
    return path


def _mac(key: bytes, nonce: str) -> str:
    return hmac.new(key, f"social:{nonce}".encode("ascii"), hashlib.sha256).hexdigest()
