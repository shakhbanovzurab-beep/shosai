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
    }
)


class AiCallError(AppError):
    """A model call failed or was refused before it was sent; the code says which.

    `retryable` marks a failure before any byte of an answer (a refused connection, or 429,
    502, 503, 504): the same request may be sent once more (F6-C15).
    """

    def __init__(self, failure: AiFailure, *, retryable: bool = False) -> None:
        super().__init__(failure.value, STATUSES[failure])
        self.failure = failure
        self.retryable = retryable


class PaidCallError(Exception):
    """A call that failed after the provider began to charge for it: its usage is recorded.

    pyannote bills a job once it starts, whatever its end; the port writes the row with the
    outcome `failed`, then raises `AiCallError` with the failure.
    """

    def __init__(self, failure: AiFailure, usage: Usage) -> None:
        super().__init__(failure.value)
        self.failure = failure
        self.usage = usage
