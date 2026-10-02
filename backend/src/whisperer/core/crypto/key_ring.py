"""Fernet key ring for secrets stored in the database (OAuth tokens, MCP credentials).

The active key `FERNET_KEY` encrypts; the keys in `FERNET_KEYS_PREVIOUS` only decrypt.
Rotation without downtime: the new key becomes active, the old one moves to the previous
keys, stored ciphertexts are re-encrypted with `rotate`, then the old key is removed.
The variable names and the cipher are the draft's, so migrated ciphertexts decrypt.
"""

from collections.abc import Sequence
from typing import Self

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from pydantic import SecretStr

from whisperer.core.config.sections import CryptoSettings


class EncryptionKeyMissingError(Exception):
    """`FERNET_KEY` is not set, so nothing can be encrypted or decrypted."""


class UndecryptableCiphertextError(Exception):
    """No key of the ring decrypts the ciphertext: it is damaged or its key was removed."""


class FernetKeyRing:
    """Encrypts with the active key and decrypts with any key of the ring."""

    def __init__(self, active: SecretStr, previous: Sequence[SecretStr] = ()) -> None:
        keys = [active, *previous]
        self._cipher = MultiFernet([Fernet(key.get_secret_value()) for key in keys])

    @classmethod
    def from_settings(cls, settings: CryptoSettings) -> Self:
        """The ring of the configured keys; without an active key, `EncryptionKeyMissingError`."""
        if settings.fernet_key is None:
            message = "FERNET_KEY не задан: шифрование хранимых секретов недоступно"
            raise EncryptionKeyMissingError(message)
        return cls(settings.fernet_key, settings.fernet_keys_previous)

    def encrypt(self, plaintext: str) -> bytes:
        """The ciphertext of the text under the active key."""
        return self._cipher.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        """The text of a ciphertext made with any key of the ring."""
        try:
            return self._cipher.decrypt(ciphertext).decode()
        except InvalidToken:
            message = "шифртекст не расшифровывается ни одним ключом кольца"
            raise UndecryptableCiphertextError(message) from None

    def rotate(self, ciphertext: bytes) -> bytes:
        """The same secret re-encrypted under the active key, without revealing it."""
        try:
            return self._cipher.rotate(ciphertext)
        except InvalidToken:
            message = "шифртекст не расшифровывается ни одним ключом кольца"
            raise UndecryptableCiphertextError(message) from None
