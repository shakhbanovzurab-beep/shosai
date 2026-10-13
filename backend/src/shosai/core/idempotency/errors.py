"""Errors of the effect-key ledger: a key reused for another request, a misused ledger."""

from http import HTTPStatus

from shosai.core.kernel.errors import AppError


class IdempotencyKeyReusedError(AppError):
    """The key was already used for a different request: the client must pick a new key."""

    def __init__(self) -> None:
        super().__init__("idempotency_key_reused", HTTPStatus.UNPROCESSABLE_ENTITY)


class ReadOnlyEffectTransactionError(Exception):
    """An effect key cannot be recorded in a read-only transaction."""


class UnfinishedEffectKeyError(Exception):
    """A committed key has no outcome: the effect's failure was swallowed and committed."""
