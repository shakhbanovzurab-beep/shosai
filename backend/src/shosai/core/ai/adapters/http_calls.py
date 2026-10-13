"""One HTTP call to a provider and what its failure means, shared by every HTTP adapter.

A transport error or a timeout, an error status and an answer that is not a JSON object
all leave as `AiCallError` with a closed code. The answer's text may hold a piece of the
request, so only its status and length are logged.
"""

from typing import Any, Final

import httpx
import structlog

from shosai.core.ai.calls import Provider
from shosai.core.ai.errors import AiCallError, AiFailure

type Json = dict[str, Any]

STATUS_FAILURES: Final = {
    404: AiFailure.MODEL_UNAVAILABLE,
    408: AiFailure.DEADLINE_EXCEEDED,
    429: AiFailure.RATE_LIMITED,
    504: AiFailure.DEADLINE_EXCEEDED,
}
# Ответ без тела успеха, после которого тот же запрос можно отправить ещё раз (F6-C15).
RETRYABLE_STATUSES: Final = frozenset({429, 502, 503, 504})
CONTEXT_MARKERS: Final = ("context length", "context_length", "maximum context")
MODERATION_MARKERS: Final = ("moderation", "flagged")
log = structlog.stdlib.get_logger(__name__)


def failure_of(status: int, text: str) -> AiFailure:
    """The call failure an error answer means."""
    lowered = text.lower()
    if status == 400 and any(marker in lowered for marker in CONTEXT_MARKERS):
        return AiFailure.CONTEXT_LENGTH_EXCEEDED
    if status == 403 and any(marker in lowered for marker in MODERATION_MARKERS):
        return AiFailure.CONTENT_REFUSED
    return STATUS_FAILURES.get(status, AiFailure.PROVIDER_ERROR)


def failed(provider: Provider, status: int, text: str) -> AiCallError:
    """The error of a failed answer, logged by status and length only."""
    failure = failure_of(status, text)
    log.warning(
        "Провайдер ИИ ответил ошибкой", provider=provider.value, status=status,
        failure=failure.value, length=len(text),
    )  # fmt: skip
    return AiCallError(failure, retryable=status in RETRYABLE_STATUSES)


async def call_json(client: httpx.AsyncClient, provider: Provider, request: httpx.Request) -> Json:
    """Send the request; the answer as a JSON object, or `AiCallError`."""
    try:
        response = await client.send(request)
    except httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout:
        # Запрос не ушёл: повтор безопасен.
        raise AiCallError(AiFailure.PROVIDER_ERROR, retryable=True) from None
    except httpx.TimeoutException:
        raise AiCallError(AiFailure.DEADLINE_EXCEEDED) from None
    except httpx.TransportError:
        raise AiCallError(AiFailure.PROVIDER_ERROR) from None
    if not response.is_success:
        raise failed(provider, response.status_code, response.text)
    try:
        answer = response.json()
    except ValueError:
        raise AiCallError(AiFailure.PROVIDER_ERROR) from None
    if not isinstance(answer, dict) or "error" in answer:
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    return answer
