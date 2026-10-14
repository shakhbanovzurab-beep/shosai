"""Errors of the native sign-in routes, with the `detail` strings shipped clients read.

The macOS and Windows 1.4.5 clients, the draft's SPA and the Obsidian plugin branch on
these exact strings (ADR 0008: the envelope keeps the draft's `detail`). Each has its own
code for v2's clients; tests pin every pair.
"""

from http import HTTPStatus
from typing import Final

from shosai.core.kernel.errors import AppError
from shosai.features.identity.domain.accounts import SignInRefusal

# Код v2 → строка detail черновика (пары, а не литерал словаря: так их читает и Bandit).
UNAUTHORIZED: Final = dict(
    (
        ("invalid_credentials", "Invalid email or password"),
        ("refresh_missing", "Missing refresh cookie"),
        ("refresh_expired", "Refresh token expired"),
        ("refresh_invalid", "Invalid refresh token"),
        ("user_not_found", "User not found"),
        ("token_revoked", "Token revoked"),
        ("token_expired", "Token expired"),
        ("token_invalid", "Invalid token"),
    )
)


def unauthorized(code: str) -> AppError:
    """401 with the draft's `detail` for the code."""
    return AppError(code, HTTPStatus.UNAUTHORIZED, detail=UNAUTHORIZED[code])


def refused(refusal: SignInRefusal) -> AppError:
    """403 `account_banned`, `account_frozen` or `account_disabled`, code and detail alike."""
    return AppError(refusal.value, HTTPStatus.FORBIDDEN, detail=refusal.value)


def email_not_verified() -> AppError:
    """403 `email_not_verified`: the password is a pending registration's; enter the code."""
    return AppError("email_not_verified", HTTPStatus.FORBIDDEN, detail="email_not_verified")


def captcha_failed() -> AppError:
    """400 `captcha_failed`: the captcha is due and the token did not pass."""
    return AppError("captcha_failed", HTTPStatus.BAD_REQUEST, detail="captcha_failed")


def csrf_mismatch() -> AppError:
    """403 `CSRF mismatch`: the header does not repeat the cookie."""
    return AppError("csrf_mismatch", HTTPStatus.FORBIDDEN, detail="CSRF mismatch")
