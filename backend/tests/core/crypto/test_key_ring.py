"""Secrets are encrypted with the active key and survive a key rotation."""

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from shosai.core.config.sections import CryptoSettings
from shosai.core.crypto.key_ring import (
    EncryptionKeyMissingError,
    FernetKeyRing,
    UndecryptableCiphertextError,
)

OLD_KEY = SecretStr(Fernet.generate_key().decode())
NEW_KEY = SecretStr(Fernet.generate_key().decode())
SECRET = "oauth-refresh-token-value"


def test_a_secret_round_trips() -> None:
    ring = FernetKeyRing(NEW_KEY)

    ciphertext = ring.encrypt(SECRET)

    assert SECRET.encode() not in ciphertext
    assert ring.decrypt(ciphertext) == SECRET


def test_after_rotation_old_ciphertexts_still_decrypt() -> None:
    old_ciphertext = FernetKeyRing(OLD_KEY).encrypt(SECRET)

    rotated_ring = FernetKeyRing(NEW_KEY, [OLD_KEY])

    assert rotated_ring.decrypt(old_ciphertext) == SECRET


def test_rotate_moves_a_ciphertext_to_the_active_key() -> None:
    old_ciphertext = FernetKeyRing(OLD_KEY).encrypt(SECRET)

    rotated = FernetKeyRing(NEW_KEY, [OLD_KEY]).rotate(old_ciphertext)

    assert FernetKeyRing(NEW_KEY).decrypt(rotated) == SECRET


def test_a_ciphertext_of_a_removed_key_is_refused() -> None:
    old_ciphertext = FernetKeyRing(OLD_KEY).encrypt(SECRET)

    with pytest.raises(UndecryptableCiphertextError):
        FernetKeyRing(NEW_KEY).decrypt(old_ciphertext)
    with pytest.raises(UndecryptableCiphertextError):
        FernetKeyRing(NEW_KEY).rotate(old_ciphertext)


def test_a_damaged_ciphertext_is_refused() -> None:
    with pytest.raises(UndecryptableCiphertextError):
        FernetKeyRing(NEW_KEY).decrypt(b"not-a-fernet-token")


def test_ciphertexts_of_the_draft_decrypt() -> None:
    # Черновик шифровал тем же Fernet: Fernet(key).encrypt(raw.encode()).
    draft_ciphertext = Fernet(OLD_KEY.get_secret_value()).encrypt(SECRET.encode())

    assert FernetKeyRing(NEW_KEY, [OLD_KEY]).decrypt(draft_ciphertext) == SECRET


def test_the_ring_is_built_from_the_settings() -> None:
    settings = CryptoSettings.model_validate(
        {
            "fernet_key": NEW_KEY.get_secret_value(),
            "fernet_keys_previous": OLD_KEY.get_secret_value(),
        }
    )
    old_ciphertext = FernetKeyRing(OLD_KEY).encrypt(SECRET)

    assert FernetKeyRing.from_settings(settings).decrypt(old_ciphertext) == SECRET


def test_without_an_active_key_there_is_no_ring() -> None:
    with pytest.raises(EncryptionKeyMissingError):
        FernetKeyRing.from_settings(CryptoSettings())
