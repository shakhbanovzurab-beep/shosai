"""Rules of a registration before the account exists (ADR 0045 point 3; draft spec 001).

Every registration has its own id, returned only to the browser that started it, and a
6-digit code mailed to the address. Verification needs both, so a second registration of
the same address — someone else's, with another password — cannot take over the first:
it has another id and another code. The code is stored as SHA-256 of the registration id
and the code, so equal codes of two registrations never hash alike. Five wrong codes end
a registration whatever the resends (the draft reset the counter on resend); three
resends at most, one minute apart.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.core.kernel.homes import Home

CODE_DIGITS: Final = 6
MAX_CODE_ATTEMPTS: Final = 5
MAX_RESENDS: Final = 3
RESEND_INTERVAL: Final = timedelta(minutes=1)
PENDING_LIFETIME: Final = timedelta(minutes=15)
# Версия текста согласия на обработку данных и на трансграничную передачу (журнал согласий).
CONSENT_VERSION: Final = "2026-10-14"


class DirectoryState(StrEnum):
    """The state of an address in the directory (EU home, §6)."""

    # Адрес занят подтверждённой регистрацией, аккаунт в доме ещё пишется.
    CLAIMED = "claimed"
    ACTIVE = "active"
    FROZEN = "frozen"
    BANNED = "banned"
    DELETION_SCHEDULED = "deletion_scheduled"
    TRANSFERRING = "transferring"
    DELETED = "deleted"


class ConsentKind(StrEnum):
    """What a person consented to; each change is a row of the consent journal."""

    PERSONAL_DATA = "personal_data"
    CROSS_BORDER = "cross_border"
    MARKETING = "marketing"
    IMPROVE_MODELS = "improve_models"
    SHARE_LOCATION = "share_location"


class RegistrationProblem(StrEnum):
    """Why a registration form is refused; the value is the client's error code."""

    PERSONAL_DATA_CONSENT_REQUIRED = "personal_data_consent_required"
    CROSS_BORDER_CONSENT_REQUIRED = "cross_border_consent_required"


@dataclass(frozen=True, slots=True)
class RegistrationConsents:
    """The consents given on the registration form."""

    personal_data: bool
    cross_border: bool
    marketing: bool

    def problem(self, home: Home) -> RegistrationProblem | None:
        """Personal data always; cross-border transfer for the Russian home (nfr-14, ID-D2)."""
        if not self.personal_data:
            return RegistrationProblem.PERSONAL_DATA_CONSENT_REQUIRED
        if home is Home.RU and not self.cross_border:
            return RegistrationProblem.CROSS_BORDER_CONSENT_REQUIRED
        return None

    def granted(self) -> tuple[ConsentKind, ...]:
        """The kinds the journal records as granted at registration."""
        given = {
            ConsentKind.PERSONAL_DATA: self.personal_data,
            ConsentKind.CROSS_BORDER: self.cross_border,
            ConsentKind.MARKETING: self.marketing,
        }
        return tuple(kind for kind, value in given.items() if value)


def new_code() -> str:
    """A uniformly random 6-digit code."""
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def code_hash(registration_id: UUID, code: str) -> bytes:
    """SHA-256 of the registration id and the code."""
    return hashlib.sha256(registration_id.bytes + code.encode("ascii")).digest()


def code_matches(registration_id: UUID, code: str, stored: bytes) -> bool:
    """Whether the code is this registration's, compared in constant time."""
    if len(code) != CODE_DIGITS or not (code.isascii() and code.isdigit()):
        return False
    return secrets.compare_digest(code_hash(registration_id, code), stored)
