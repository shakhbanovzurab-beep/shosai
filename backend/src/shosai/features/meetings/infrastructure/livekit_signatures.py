"""LiveKit's webhook signatures, checked here rather than by the SDK's receiver (meetings A2).

The JWT is verified with the API's key and secret, and the body's SHA-256 is compared with the
token's claim in constant time; a body that is not a webhook is refused as well. Each answer is
counted, for the alert on more than 1 % of webhooks failing verification.
"""

import base64
import binascii
import hashlib
import hmac
from typing import Final

import jwt
import structlog
from livekit.api.access_token import TokenVerifier
from pydantic import ValidationError

from shosai.features.meetings.application.video_server import SfuWebhook, WebhookRejectedError
from shosai.features.meetings.infrastructure.livekit_metrics import LiveKitMetrics
from shosai.features.meetings.infrastructure.livekit_wire import webhook_of

BEARER: Final = "Bearer "
log = structlog.stdlib.get_logger(__name__)


def verified_webhook(
    verifier: TokenVerifier, metrics: LiveKitMetrics, body: bytes, authorization: str | None
) -> SfuWebhook:
    """The webhook if it is signed over this body; `WebhookRejectedError` otherwise."""
    token = (authorization or "").removeprefix(BEARER).strip()
    try:
        claims = verifier.verify(token)
        claimed = base64.b64decode(claims.sha256 or "", validate=True)
    except (jwt.PyJWTError, binascii.Error) as error:
        raise _rejected(metrics, type(error).__qualname__) from error
    if not claimed or not hmac.compare_digest(hashlib.sha256(body).digest(), claimed):
        raise _rejected(metrics, "body_hash_mismatch")
    try:
        webhook = webhook_of(body)
    except ValidationError as error:
        raise _rejected(metrics, type(error).__qualname__) from error
    metrics.webhook_verified(accepted=True)
    return webhook


def _rejected(metrics: LiveKitMetrics, reason: str) -> WebhookRejectedError:
    metrics.webhook_verified(accepted=False)
    log.warning("Вебхук LiveKit отклонён", reason=reason)
    return WebhookRejectedError()
