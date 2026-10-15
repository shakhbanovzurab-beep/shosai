"""The admin's sign-in, session check and sign-out (ADR 0049).

The login and the bcrypt hash of the password come from the environment. Every attempt
checks both — a wrong login still spends a bcrypt check — so the answer's timing does not
tell which one was wrong. The route limits attempts per address; here the login as a
whole is limited too, which caps guessing spread over many addresses. A failure is logged
with the client address, never with what was typed.
"""

import hmac
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
from typing import Final

import structlog
from pydantic import SecretStr

from shosai.core.kernel.errors import AppError
from shosai.core.kv.rate_limits import RateLimit, RateLimiter
from shosai.features.identity.infrastructure.admin_sessions import (
    AdminSessions,
    AdminSessionsUnavailableError,
)
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher

# На весь логин: перебор с многих адресов упирается в этот потолок.
LOGIN_LIMIT: Final = RateLimit("identity.admin_sign_in", 20, timedelta(hours=1), 10)
LOGIN_SUBJECT: Final = "admin"
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AdminCredentials:
    """The admin's login and the bcrypt hash of the password, from the environment."""

    username: str
    password_hash: SecretStr


class AdminAccess:
    """Open, check and close the admin's sessions; the `identity.admin_gate` port."""

    def __init__(
        self,
        credentials: AdminCredentials | None,
        hasher: PasswordHasher,
        sessions: AdminSessions,
        limiter: RateLimiter,
    ) -> None:
        self._credentials = credentials
        self._hasher = hasher
        self._sessions = sessions
        self._limiter = limiter

    async def sign_in(self, username: str, password: str, address: str) -> str:
        """The value of the admin cookie for correct credentials; 401 otherwise."""
        credentials = self._credentials
        if credentials is None:
            log.warning("Вход в админку отклонён: логин и хэш пароля не заданы")
            raise AppError("admin_sign_in_disabled", HTTPStatus.SERVICE_UNAVAILABLE)
        decision = await self._limiter.check(LOGIN_LIMIT, LOGIN_SUBJECT)
        if not decision.allowed:
            seconds = max(int(decision.retry_after.total_seconds()), 1)
            raise AppError(
                "rate_limited",
                HTTPStatus.TOO_MANY_REQUESTS,
                params={"retry_after_seconds": seconds},
            )
        name_matches = hmac.compare_digest(
            username.encode("utf-8"), credentials.username.encode("utf-8")
        )
        password_matches = await self._hasher.verify(
            password, credentials.password_hash.get_secret_value()
        )
        if not (name_matches and password_matches):
            log.warning("Неверный вход в админку", client_address=address)
            raise AppError("invalid_credentials", HTTPStatus.UNAUTHORIZED)
        try:
            cookie = await self._sessions.open()
        except AdminSessionsUnavailableError as error:
            raise _unavailable() from error
        log.info("Администратор вошёл в админку", client_address=address)
        return cookie

    async def admitted(self, cookie: str | None) -> bool:
        """Whether the cookie belongs to a live admin session."""
        try:
            return await self._sessions.valid(cookie)
        except AdminSessionsUnavailableError as error:
            raise _unavailable() from error

    async def sign_out(self, cookie: str | None) -> None:
        """End the session of the cookie at once; an unknown cookie changes nothing."""
        try:
            await self._sessions.close(cookie)
        except AdminSessionsUnavailableError as error:
            raise _unavailable() from error


def _unavailable() -> AppError:
    log.error("Сессии админки недоступны: Valkey не ответил")
    return AppError("admin_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)
