"""The rules of one connect flow: PKCE, the one-time state, the browser binder, the return.

A flow lives 10 minutes. Its state nonce is the key it is kept under (its SHA-256, so a
leaked store never holds a usable state); its binder travels in an httpOnly cookie of the
browser that started it, and the callback refuses a browser without it — the draft let a
link started by one person and finished by another attach the second person's account to
the first. The callback always redirects to a relative cabinet path: the popup's message is
origin-checked, and an absolute address would be an open redirect (plan §3.4).
"""

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final
from urllib.parse import urlencode

FLOW_LIFETIME: Final = timedelta(minutes=10)
# RFC 7636: верификатор 43–128 символов из алфавита unreserved.
VERIFIER: Final = re.compile(r"[A-Za-z0-9\-._~]{43,128}")
NONCE_BYTES: Final = 32
BINDER_BYTES: Final = 32
CALLBACK_PAGE: Final = "/oauth/callback"
# Куда кабинет может вернуться после входа: путь кабинета без схемы, хоста и обходов.
RETURN_PATH: Final = re.compile(r"/app(/[A-Za-z0-9\-._~%]+)*/?(\?[A-Za-z0-9\-._~%=&]*)?")
RETURN_PATH_MAX_LENGTH: Final = 512


class ReturnKind(StrEnum):
    """Where the browser goes after the provider: the popup's page, a cabinet page, chats."""

    POPUP = "popup"
    PAGE = "page"
    CHATS = "chats"


class Outcome(StrEnum):
    """How a flow ended, as `status` of the cabinet's callback page."""

    CONNECTED = "connected"
    DENIED = "denied"
    ERROR = "error"


class FlowError(StrEnum):
    """Why a flow ended in error; the cabinet words each code (plan §2, settled)."""

    AUTHORIZATION_EXPIRED = "authorization_expired"
    SCOPE_MISSING = "scope_missing"
    ADMIN_CONSENT_REQUIRED = "admin_consent_required"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    NOT_OFFERED = "not_offered"
    IMAP_DISABLED = "imap_disabled"
    PROVIDER_SUBSCRIPTION_REQUIRED = "provider_subscription_required"
    INSTALLED_ELSEWHERE = "installed_elsewhere"


class ReturnPathError(ValueError):
    """A return path that is not a plain cabinet path."""


@dataclass(frozen=True, slots=True)
class ReturnTarget:
    """Where the callback sends the browser."""

    kind: ReturnKind
    path: str | None = None

    def __post_init__(self) -> None:
        if (self.kind is ReturnKind.PAGE) != (self.path is not None):
            message = "путь возврата бывает только у возврата на страницу кабинета"
            raise ReturnPathError(message)
        if self.path is not None:
            check_return_path(self.path)


def check_return_path(path: str) -> None:
    """Refuse anything but a relative path inside the cabinet."""
    if len(path) > RETURN_PATH_MAX_LENGTH or "//" in path or ".." in path:
        message = "путь возврата не похож на путь кабинета"
        raise ReturnPathError(message)
    if not RETURN_PATH.fullmatch(path):
        message = "путь возврата — относительный путь кабинета /app/…"
        raise ReturnPathError(message)


def new_verifier() -> str:
    """A PKCE code verifier: 64 URL-safe characters from 48 random bytes."""
    return secrets.token_urlsafe(48)


def challenge_of(verifier: str) -> str:
    """The S256 code challenge of a verifier (RFC 7636 §4.2)."""
    if not VERIFIER.fullmatch(verifier):
        message = "верификатор PKCE — 43–128 символов алфавита RFC 7636"
        raise ValueError(message)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def new_nonce() -> str:
    """The state parameter of a new flow."""
    return secrets.token_urlsafe(NONCE_BYTES)


def new_binder() -> str:
    """The value of the browser-binding cookie of a new flow."""
    return secrets.token_urlsafe(BINDER_BYTES)


def digest_of(value: str) -> str:
    """The SHA-256 hex of a nonce or a binder: the form kept server-side."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def binder_matches(expected_digest: str, presented: str | None) -> bool:
    """Whether the cookie presented at the callback is the flow's own, in constant time."""
    if presented is None:
        return False
    return hmac.compare_digest(expected_digest, digest_of(presented))


def callback_location(
    target: ReturnTarget,
    app: str,
    outcome: Outcome,
    *,
    error: FlowError | None = None,
    connection_id: str | None = None,
) -> str:
    """The relative `Location` the provider callback answers with."""
    if (outcome is Outcome.ERROR) != (error is not None):
        message = "код ошибки бывает только у исхода error"
        raise ValueError(message)
    query: dict[str, str] = {"status": outcome.value}
    if error is not None:
        query["error"] = error.value
    if target.kind is ReturnKind.CHATS:
        query = {"flow": "chats", **query}
        if connection_id is not None and outcome is Outcome.CONNECTED:
            query["installation_id"] = connection_id
        return f"{CALLBACK_PAGE}?{urlencode(query)}"
    query = {"connector": app, **query}
    if target.kind is ReturnKind.PAGE and target.path is not None:
        separator = "&" if "?" in target.path else "?"
        return f"{target.path}{separator}{urlencode(query)}"
    return f"{CALLBACK_PAGE}?{urlencode(query)}"
