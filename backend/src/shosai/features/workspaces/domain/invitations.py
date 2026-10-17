"""Invitation links: one-time, bound to an address, 14 days (ADR 0053 point 3).

The link carries 32 random bytes; only their SHA-256 is stored, so a database read
cannot rebuild a link. A resend issues new bytes and voids the old link. The randomness
comes from the caller, so these rules stay pure and testable.
"""

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

INVITATION_LIFETIME: Final = timedelta(days=14)
TOKEN_BYTES: Final = 32
# Не больше 20 адресов за раз — как в окне приглашения кабинета.
EMAILS_PER_REQUEST_MAX: Final = 20
# base64url без выравнивания для 32 байт.
TOKEN_LENGTH: Final = 43


class InvalidInvitationTokenError(ValueError):
    """The text is not an invitation token."""


@dataclass(frozen=True, slots=True)
class InvitationToken:
    """The secret part of an invitation link."""

    value: str

    @classmethod
    def from_random(cls, random_bytes: bytes) -> InvitationToken:
        """A token from exactly 32 random bytes."""
        if len(random_bytes) != TOKEN_BYTES:
            message = f"токен приглашения — ровно {TOKEN_BYTES} случайных байт"
            raise InvalidInvitationTokenError(message)
        return cls(base64.urlsafe_b64encode(random_bytes).rstrip(b"=").decode("ascii"))

    @classmethod
    def parse(cls, text: str) -> InvitationToken:
        """A token as a link brings it back; anything else is refused before any lookup."""
        if len(text) != TOKEN_LENGTH:
            raise InvalidInvitationTokenError
        try:
            raw = base64.urlsafe_b64decode(f"{text}=")
        except ValueError as error:
            raise InvalidInvitationTokenError from error
        if len(raw) != TOKEN_BYTES or cls.from_random(raw).value != text:
            raise InvalidInvitationTokenError
        return cls(text)

    def digest(self) -> bytes:
        """What the database stores and looks the invitation up by."""
        return hashlib.sha256(self.value.encode("ascii")).digest()

    def matches(self, stored_digest: bytes) -> bool:
        """Whether this token is the one a stored digest was made from."""
        return hmac.compare_digest(self.digest(), stored_digest)


def expires_at(sent_at: datetime) -> datetime:
    """When a link sent at this moment stops working."""
    return sent_at + INVITATION_LIFETIME


def is_expired(sent_at: datetime, now: datetime) -> bool:
    """Whether a link sent at `sent_at` no longer works at `now`."""
    return now >= expires_at(sent_at)
