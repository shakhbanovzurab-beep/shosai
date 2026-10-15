"""The errors registration answers with; the client turns each code into text (ADR 0008)."""

from http import HTTPStatus

from shosai.core.kernel.errors import AppError


def invalid(code: str) -> AppError:
    """422: the form breaks a rule; the code names the rule."""
    return AppError(code, HTTPStatus.UNPROCESSABLE_ENTITY)


def captcha_failed() -> AppError:
    """400 `captcha_failed`, as the draft and its clients know it."""
    return AppError("captcha_failed", HTTPStatus.BAD_REQUEST)


def invalid_code() -> AppError:
    """400: the code is wrong, or the registration expired or never was."""
    return AppError("invalid_code", HTTPStatus.BAD_REQUEST)


def registration_locked() -> AppError:
    """400: five wrong codes ended this registration; the person registers again."""
    return AppError("registration_locked", HTTPStatus.BAD_REQUEST)


def email_registered() -> AppError:
    """409: another registration of the address was confirmed first."""
    return AppError("email_registered", HTTPStatus.CONFLICT)


def resend_refused(code: str, retry_after_seconds: int) -> AppError:
    """429: no more resends now (`resend_too_soon`) or ever (`too_many_resends`)."""
    return AppError(
        code,
        HTTPStatus.TOO_MANY_REQUESTS,
        params={"retry_after_seconds": max(retry_after_seconds, 1)},
    )


def registration_unavailable() -> AppError:
    """503: Valkey, which routes registrations to their home, did not answer."""
    return AppError(
        "registration_unavailable",
        HTTPStatus.SERVICE_UNAVAILABLE,
        params={"retry_after_seconds": 5},
    )


def code_locked() -> AppError:
    """400: five wrong codes ended this sign-in by email; the person asks for a new code."""
    return AppError("code_locked", HTTPStatus.BAD_REQUEST)


def sign_in_unavailable() -> AppError:
    """503: Valkey, which counts the codes of sign-in by email, did not answer."""
    return AppError(
        "sign_in_unavailable",
        HTTPStatus.SERVICE_UNAVAILABLE,
        params={"retry_after_seconds": 5},
    )
