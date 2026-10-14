"""Reset links: one use, 60 minutes, a new one voids the older ones (draft spec 001, ADR 0045).

The link carries a random secret and the home of its account in the clear, because a
reset arrives without a session and must reach the right home; the home is no secret.
Only SHA-256 of the secret is stored, so a copy of the table opens no account.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from shosai.core.kernel.homes import Home

RESET_LIFETIME: Final = timedelta(minutes=60)
SECRET_BYTES: Final = 32
SEPARATOR: Final = "_"


@dataclass(frozen=True, slots=True)
class ResetToken:
    """The secret of a reset link and the home of its account."""

    home: Home
    secret: str

    @property
    def text(self) -> str:
        """The token as the link carries it: `ru_<secret>`."""
        return f"{self.home.value}{SEPARATOR}{self.secret}"

    @property
    def digest(self) -> bytes:
        """SHA-256 of the secret, as the table stores it."""
        return hashlib.sha256(self.secret.encode("ascii")).digest()


def new_reset_token(home: Home) -> ResetToken:
    """A new random reset token for an account of the home."""
    return ResetToken(home, secrets.token_urlsafe(SECRET_BYTES))


def parse_reset_token(text: str) -> ResetToken | None:
    """The token of a link, or None for text that is not one."""
    home, separator, secret = text.partition(SEPARATOR)
    if not separator or home not in Home or not secret or not secret.isascii():
        return None
    return ResetToken(Home(home), secret)
