"""The key of a record's state hash, derived from the platform's Fernet key (ADR 0069 DL-D7).

A record keeps an HMAC of the state, never the state: equal states match in replay, and the
hash cannot be reversed by guessing. The key is derived from `FERNET_KEY` with HKDF under
this purpose's own label, so no new secret is needed and the derived key is useless for
anything else. Without `FERNET_KEY` (development) records keep no hash. Rotating the Fernet
key changes the derived one: hashes stay comparable within the 90 days records live only
between rotations, which is all replay needs.
"""

from typing import Final

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from shosai.core.config.sections import CryptoSettings

PURPOSE: Final = b"shosai decisions state hash v1"
KEY_BYTES: Final = 32


def state_hash_key(crypto: CryptoSettings) -> bytes | None:
    """The derived key, or None while no Fernet key is set."""
    if crypto.fernet_key is None:
        return None
    root = crypto.fernet_key.get_secret_value().encode()
    return HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=None, info=PURPOSE).derive(root)
