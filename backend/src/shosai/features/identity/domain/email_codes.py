"""Sign-in by an emailed code (ADR 0048): the code, its lifetime and how it is checked.

A challenge is one address asking to come in. The browser holds it sealed — the address
travels inside, encrypted — and Valkey holds only its state: the code's hash, the attempts
and the resends. Five wrong codes end it; new codes follow the registration's pacing.
"""

import hashlib
import secrets
from datetime import timedelta
from typing import Final

from shosai.features.identity.domain.registration import CODE_DIGITS

CHALLENGE_LIFETIME: Final = timedelta(minutes=15)
MAX_ATTEMPTS: Final = 5
NONCE_BYTES: Final = 16


def new_nonce() -> bytes:
    """The random identity of a challenge."""
    return secrets.token_bytes(NONCE_BYTES)


def challenge_code_hash(nonce: bytes, code: str) -> bytes:
    """SHA-256 of the challenge's nonce and the code."""
    return hashlib.sha256(nonce + code.encode("ascii")).digest()


def challenge_code_matches(nonce: bytes, code: str, stored: bytes) -> bool:
    """Whether the code is the challenge's, compared in constant time."""
    if len(code) != CODE_DIGITS or not (code.isascii() and code.isdigit()):
        return False
    return secrets.compare_digest(challenge_code_hash(nonce, code), stored)
