"""The directory key: the only trace of an email outside its home (§6, nfr-4, inv-2)."""

import hashlib
import hmac
from typing import Final

from shosai.features.identity.domain.emails import NormalizedEmail

DIRECTORY_KEY_MIN_BYTES: Final = 32


def email_hmac(key: bytes, email: NormalizedEmail) -> bytes:
    """HMAC-SHA256 of the normalised address under the directory key (32 bytes)."""
    return hmac.new(key, email.value.encode("utf-8"), hashlib.sha256).digest()
