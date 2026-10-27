"""The key of the profile core's boundary, derived from the platform's Fernet key (ADR 0071).

Segment 4's memory block is wrapped with an HMAC of its own text: stable while the facts are,
so the provider's prefix cache holds, and unknowable to whoever wrote a fact. The key is
derived from `FERNET_KEY` with HKDF under this purpose's own label, so no new secret is kept;
without `FERNET_KEY` (development) a process draws its own, and the cache holds within it.
"""

import secrets
from typing import Final

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from shosai.core.config.sections import CryptoSettings

PURPOSE: Final = b"shosai agent profile boundary v1"
KEY_BYTES: Final = 32


def profile_boundary_key(crypto: CryptoSettings) -> bytes:
    """The derived key, or a key of this process while no Fernet key is set."""
    if crypto.fernet_key is None:
        return secrets.token_bytes(KEY_BYTES)
    root = crypto.fernet_key.get_secret_value().encode()
    return HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=None, info=PURPOSE).derive(root)
