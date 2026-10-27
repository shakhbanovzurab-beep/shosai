"""The invitation token: the secret part of a room's one link (meetings plan §1.2, MR-D1).

A new room gets 12 URL-safe characters (72 random bits): unguessable at the join's limit of
10 attempts a minute per address. The draft's rooms keep their tokens verbatim, up to 64
characters, and their links keep working (R1). A token never expires; the room's state
decides what its link answers. `/meet/{token}` is the canonical link; `/j/{token}` and
`/rooms/join/{token}`, already sent in emails and calendars, live forever.
"""

import re
import secrets
from typing import Final

INVITE_BYTES: Final = 9
INVITE_TOKEN: Final = re.compile(r"[A-Za-z0-9_-]{12,64}")
# Канонический путь ссылки и пути, уже разосланные черновиком.
LINK_PATH: Final = "/meet/"
LEGACY_LINK_PATHS: Final = ("/j/", "/rooms/join/")
# Страница входа кабинета, на которую край отправляет все три пути (A10).
JOIN_PAGE_PATH: Final = "/app/meet/"


def new_invite_token() -> str:
    """A fresh token of 12 URL-safe characters."""
    return secrets.token_urlsafe(INVITE_BYTES)


def is_invite_token(value: str) -> bool:
    """Whether a string can be a token; anything else is refused before a lookup."""
    return INVITE_TOKEN.fullmatch(value) is not None


def room_link(origin: str, token: str) -> str:
    """The room's link at the platform's public origin, e.g. `https://shosai.tech/meet/…`."""
    return f"{origin.rstrip('/')}{LINK_PATH}{token}"
