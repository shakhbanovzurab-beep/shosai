"""Why a model call did not produce a result: a closed set of codes (F6 plan §3.3)."""

from enum import StrEnum
from http import HTTPStatus
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from shosai.core.kernel.errors import AppError

if TYPE_CHECKING:
    # Только для аннотации: результаты сами ссылаются на коды отказа.
    from shosai.core.ai.results import Usage


class AiFailure(StrEnum):
    """The codes a caller sees; a slice maps them to its own behaviour or passes them on."""

    MODEL_UNPRICED = "model_unpriced"
    MODEL_UNAVAILABLE = "model_unavailable"
    CONSENT_REQUIRED = "consent_required"
    RATE_LIMITED = "rate_limited"
    CONTEXT_LENGTH_EXCEEDED = "context_length_exceeded"
    CONTENT_REFUSED = "content_refused"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    PROVIDER_ERROR = "provider_error"
    # Провайдер занят до предела или защита недоступна: повторить позже.
    RETRY_LATER = "retry_later"
    # Достигнут потолок расходов: пользователя, аккаунта платформы или общий.
    SPEND_LIMIT = "spend_limit"
    # Дорогие вызовы приостановлены аварийным выключателем или без Valkey (§13.2).
    EXPENSIVE_PAUSED = "expensive_paused"
    # Вход больше допустимого: контекст, число или размер картинок (F6-D6).
    INPUT_TOO_LARGE = "input_too_large"


STATUSES: Final = MappingProxyType(
    {
        AiFailure.MODEL_UNPRICED: HTTPStatus.SERVICE_UNAVAILABLE,
        AiFailure.MODEL_UNAVAILABLE: HTTPStatus.SERVICE_UNAVAILABLE,
        AiFailure.CONSENT_REQUIRED: HTTPStatus.FORBIDDEN,
        AiFailure.RATE_LIMITED: HTTPStatus.TOO_MANY_REQUESTS,
        AiFailure.CONTEXT_LENGTH_EXCEEDED: HTTPStatus.UNPROCESSABLE_ENTITY,
        AiFailure.CONTENT_REFUSED: HTTPStatus.UNPROCESSABLE_ENTITY,
        AiFailure.DEADLINE_EXCEEDED: HTTPStatus.GATEWAY_TIMEOUT,
        AiFailure.PROVIDER_ERROR: HTTPStatus.BAD_GATEWAY,
        AiFailure.RETRY_LATER: HTTPStatus.SERVICE_UNAVAILABLE,
        AiFailure.SPEND_LIMIT: HTTPStatus.PAYMENT_REQUIRED,
        AiFailure.EXPENSIVE_PAUSED: HTTPStatus.SERVICE_UNAVAILABLE,
        AiFailure.INPUT_TOO_LARGE: HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    }
)
# Что модель читает, когда её вызов инструмента не удался по этой причине (CLAUDE.md,
# «Prompts»: текст для модели — английский; тест реестра это проверяет).
MODEL_TEXTS: Final = MappingProxyType(
    {
        AiFailure.MODEL_UNPRICED: "This model cannot be used right now.",
        AiFailure.MODEL_UNAVAILABLE: "This model is unavailable right now.",
        AiFailure.CONSENT_REQUIRED: "The user has not allowed their data to leave their country.",
        AiFailure.RATE_LIMITED: "Too many requests at once; try again in a few seconds.",
        AiFailure.CONTEXT_LENGTH_EXCEEDED: "The input is longer than the model accepts.",
        AiFailure.CONTENT_REFUSED: "The provider refused this content.",
        AiFailure.DEADLINE_EXCEEDED: "The model did not answer in time.",
        AiFailure.PROVIDER_ERROR: "The model provider failed; the request did not complete.",
        AiFailure.RETRY_LATER: "The service is busy; try again later.",
        AiFailure.SPEND_LIMIT: "The spending limit for AI has been reached.",
        AiFailure.EXPENSIVE_PAUSED: "Premium AI features are paused right now.",
        AiFailure.INPUT_TOO_LARGE: (
            "The request is too large: shorten the conversation, or attach fewer or smaller images."
        ),
    }
)


class AiCallError(AppError):
    """A model call failed or was refused before it was sent; the code says which.

    `retryable` marks a failure before any byte of an answer (a refused connection, or 429,
    502, 503, 504): the same request may be sent once more (F6-C15).
    """

    def __init__(
        self, failure: AiFailure, *, retryable: bool = False, retry_after: int | None = None
    ) -> None:
        params = {"retry_after_seconds": retry_after} if retry_after is not None else None
        super().__init__(failure.value, STATUSES[failure], params=params)
        self.failure = failure
        self.retryable = retryable

    @property
    def model_text(self) -> str:
        """The failure in English, for a model whose tool call it ended."""
        return MODEL_TEXTS[self.failure]


class PaidCallError(Exception):
    """A call that failed after the provider began to charge for it: its usage is recorded.

    pyannote bills a job once it starts, whatever its end; the port writes the row with the
    outcome `failed`, then raises `AiCallError` with the failure.
    """

    def __init__(self, failure: AiFailure, usage: Usage) -> None:
        super().__init__(failure.value)
        self.failure = failure
        self.usage = usage
