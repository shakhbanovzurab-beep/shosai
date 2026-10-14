"""Cloudflare Turnstile, the only captcha (ADR 0045 point 4).

The server asks `siteverify` and lets the form through only on `success: true`; any other
answer, a timeout or a network failure refuses it (fail closed, as the draft). A token is
single-use and Cloudflare may already have spent it when a read times out, so only a
failed connection is retried, once. The request leaves over IPv4: the draft's host had no
IPv6 route while Cloudflare publishes AAAA records, and every call hung until the timeout.
Without a secret (development only; the gate requires it elsewhere) the check is off.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final, Protocol

import httpx
import structlog
from pydantic import SecretStr

SITEVERIFY_URL: Final = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TIMEOUT: Final = httpx.Timeout(5.0, connect=2.0)
MAX_TOKEN_LENGTH: Final = 4096
log = structlog.stdlib.get_logger(__name__)


class Captcha(Protocol):
    """Whether a form's captcha token proves a person."""

    async def passed(self, token: str | None, remote_address: str) -> bool:
        """True only when the provider confirmed the token."""
        ...


class CaptchaOff:
    """No captcha: development without a Turnstile secret."""

    async def passed(self, token: str | None, remote_address: str) -> bool:
        """Every form passes."""
        del token, remote_address
        return True


class Turnstile:
    """Server-side verification of Turnstile tokens."""

    def __init__(self, client: httpx.AsyncClient, secret: SecretStr) -> None:
        self._client = client
        self._secret = secret

    async def passed(self, token: str | None, remote_address: str) -> bool:
        """Ask Cloudflare; refuse on anything but an explicit success."""
        if not token or len(token) > MAX_TOKEN_LENGTH:
            return False
        form = {
            "secret": self._secret.get_secret_value(),
            "response": token,
            "remoteip": remote_address,
        }
        for attempt in (1, 2):
            try:
                response = await self._client.post(SITEVERIFY_URL, data=form)
            except httpx.ConnectError:
                if attempt == 1:
                    continue
                log.warning("Turnstile недоступен, капча не пройдена")
                return False
            except httpx.HTTPError as error:
                log.warning("Проверка Turnstile не завершилась", error=type(error).__name__)
                return False
            return _succeeded(response)
        return False


@asynccontextmanager
async def open_captcha(secret: SecretStr | None) -> AsyncIterator[Captcha]:
    """Turnstile with its own HTTP client over IPv4, or no captcha without a secret."""
    if secret is None:
        log.info("Капча выключена: секрет Turnstile не задан")
        yield CaptchaOff()
        return
    # S104/B104 — ложное срабатывание: это адрес-источник исходящего соединения (любой IPv4),
    # а не прослушивание всех интерфейсов.
    transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=0)  # noqa: S104  # nosec B104
    async with httpx.AsyncClient(transport=transport, timeout=TIMEOUT) as client:
        yield Turnstile(client, secret)


def _succeeded(response: httpx.Response) -> bool:
    if response.status_code != httpx.codes.OK:
        log.warning("Turnstile ответил ошибкой", status=response.status_code)
        return False
    try:
        payload = response.json()
    except ValueError:
        log.warning("Ответ Turnstile не JSON")
        return False
    return isinstance(payload, dict) and payload.get("success") is True
