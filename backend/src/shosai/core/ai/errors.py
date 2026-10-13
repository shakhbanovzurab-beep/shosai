"""Why a model call did not produce a result: a closed set of codes (F6 plan §3.3)."""

from enum import StrEnum
from http import HTTPStatus
from types import MappingProxyType
from typing import Final

from shosai.core.kernel.errors import AppError


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
    }
)


class AiCallError(AppError):
    """A model call failed or was refused before it was sent; the code says which."""

    def __init__(self, failure: AiFailure) -> None:
        super().__init__(failure.value, STATUSES[failure])
        self.failure = failure
