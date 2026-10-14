"""The consent ticket: who a new person is, until they accept the terms (ADR 0045).

A person unknown to Shosai signs in at a provider, then sees the consent screen. What the
provider said — the address, the name, the provider's user id — must wait for them, but
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
    """The provider's identity of a new person and where they were going."""

    identity: SocialIdentity
    next_path: str
    language: str


class ConsentTickets:
    """Seal and open consent tickets."""

    def __init__(self, signing_key: bytes) -> None:
        derived = hashlib.sha256(DERIVATION + signing_key).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(derived))

    def seal(self, claim: ConsentClaim) -> str:
        """The ticket the consent screen carries."""
        identity = claim.identity
        payload = {
            "provider": identity.provider.value, "subject": identity.subject,
            "email": identity.email, "verified": identity.email_verified,
            "name": identity.display_name, "next": claim.next_path, "language": claim.language,
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
        identity = SocialIdentity(
            provider=Provider(payload["provider"]),
            subject=payload["subject"],
            email=payload["email"],
            email_verified=bool(payload["verified"]),
            display_name=payload["name"],
        )
        return ConsentClaim(identity, payload["next"], payload["language"])
