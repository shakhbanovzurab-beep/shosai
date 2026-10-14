"""Password rules (ADR 0045; draft spec 001).

Length is the whole policy, as in the draft: 8 to 256 characters for a new password, 1 to
256 for a sign-in attempt. bcrypt reads at most 72 bytes; the draft's bcrypt 4 dropped the
rest silently, so its hashes were computed over the first 72 UTF-8 bytes. bcrypt 5
refuses a longer input instead, and identity passes exactly those 72 bytes, so every
migrated hash keeps verifying and a long password still works.
"""

from enum import StrEnum
from typing import Final

MIN_NEW_PASSWORD_LENGTH: Final = 8
MAX_PASSWORD_LENGTH: Final = 256
BCRYPT_INPUT_BYTES: Final = 72


class PasswordProblem(StrEnum):
    """Why a new password is refused; the value is the client's error code."""

    TOO_SHORT = "password_too_short"
    TOO_LONG = "password_too_long"


def new_password_problem(password: str) -> PasswordProblem | None:
    """The rule a new password breaks, or None."""
    if len(password) < MIN_NEW_PASSWORD_LENGTH:
        return PasswordProblem.TOO_SHORT
    if len(password) > MAX_PASSWORD_LENGTH:
        return PasswordProblem.TOO_LONG
    return None


def bcrypt_input(password: str) -> bytes:
    """The bytes bcrypt hashes: the first 72 bytes of the UTF-8 encoding."""
    return password.encode("utf-8")[:BCRYPT_INPUT_BYTES]
