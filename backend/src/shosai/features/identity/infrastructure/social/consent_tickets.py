"""The consent ticket: who a new person is, until they accept the terms (ADR 0045, 0048).

A person unknown to Shosai signs in at a provider or confirms an address by an emailed
code, then sees the consent screen. What is known of them — the address, the name, the
provider's user id — must wait for them, but
must not wait in Valkey in the EU (personal data of Russian users). It travels in the
URL as a Fernet token under a key derived from the signing key: encrypted, signed and
expiring in 10 minutes; Valkey only marks its hash spent, so it opens one account once.
"""

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from cryptography.fernet import Fernet, InvalidToken

from shosai.features.identity.domain.social import Provider, SocialIdentity

CONSENT_LIFETIME: Final = timedelta(minutes=10)
DERIVATION: Final = b"shosai.identity.social_consent.v1"


@dataclass(frozen=True, slots=True)
class ConsentClaim:
    """A new person: the provider's identity, or the address they proved by a code."""

    identity: SocialIdentity | None
    next_path: str
    language: str
    # Адрес, подтверждённый кодом из письма; у входа через сервис адрес — в identity.
    proven_email: str | None = None

    @property
    def email(self) -> str | None:
        """The address the account is created with."""
        return self.identity.email if self.identity is not None else self.proven_email

    @property
    def email_verified(self) -> bool:
        """Whether the address is proven: by the code, or by a provider that vouches for it."""
        return self.identity.email_verified if self.identity is not None else True

    @property
    def display_name(self) -> str | None:
        """The name the provider gave, if any."""
        return self.identity.display_name if self.identity is not None else None


class ConsentTickets:
    """Seal and open consent tickets."""

    def __init__(self, signing_key: bytes) -> None:
        derived = hashlib.sha256(DERIVATION + signing_key).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(derived))

    def seal(self, claim: ConsentClaim) -> str:
        """The ticket the consent screen carries."""
        identity = claim.identity
        payload = {
            "provider": identity.provider.value if identity else None,
            "subject": identity.subject if identity else None,
            "email": claim.email, "verified": claim.email_verified, "name": claim.display_name,
            "next": claim.next_path, "language": claim.language,
        }  # fmt: skip
        return self._fernet.encrypt(json.dumps(payload).encode("utf-8")).decode("ascii")

    def open(self, ticket: str) -> ConsentClaim | None:
        """The claim of a valid, unexpired ticket, or None."""
        try:
            raw = self._fernet.decrypt(
                ticket.encode("ascii"), ttl=int(CONSENT_LIFETIME.total_seconds())
            )
        except InvalidToken, UnicodeEncodeError:
            return None
        payload = json.loads(raw)
        if payload["provider"] is None:
            return ConsentClaim(None, payload["next"], payload["language"], payload["email"])
        identity = SocialIdentity(
            provider=Provider(payload["provider"]),
            subject=payload["subject"],
            email=payload["email"],
            email_verified=bool(payload["verified"]),
            display_name=payload["name"],
        )
        return ConsentClaim(identity, payload["next"], payload["language"])
