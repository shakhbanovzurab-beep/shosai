"""Turnstile fails closed and retries only a failed connection (ADR 0045 point 4)."""

from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from shosai.features.identity.infrastructure.captcha import CaptchaOff, Turnstile

SECRET = SecretStr("turnstile-secret")


def turnstile(handler: Callable[[httpx.Request], httpx.Response]) -> Turnstile:
    return Turnstile(httpx.AsyncClient(transport=httpx.MockTransport(handler)), SECRET)


async def test_only_an_explicit_success_passes() -> None:
    sent: list[bytes] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request.content)
        return httpx.Response(200, json={"success": True, "hostname": "shosai.tech"})

    assert await turnstile(answer).passed("token-1", "203.0.113.7")
    assert b"secret=turnstile-secret" in sent[0]
    assert b"remoteip=203.0.113.7" in sent[0]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"success": False, "error-codes": ["invalid-input-response"]}),
        httpx.Response(200, json={"success": "true"}),
        httpx.Response(200, text="not json"),
        httpx.Response(500, json={"success": True}),
    ],
)
async def test_anything_else_is_refused(response: httpx.Response) -> None:
    assert not await turnstile(lambda _request: response).passed("token", "203.0.113.7")


async def test_a_missing_or_huge_token_is_refused_without_asking() -> None:
    def never(_request: httpx.Request) -> httpx.Response:
        raise AssertionError

    captcha = turnstile(never)

    assert not await captcha.passed(None, "203.0.113.7")
    assert not await captcha.passed("x" * 4097, "203.0.113.7")


async def test_a_failed_connection_is_retried_once_a_timeout_never() -> None:
    calls: list[str] = []

    def flaky(request: httpx.Request) -> httpx.Response:
        calls.append("connect")
        if len(calls) == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"success": True})

    def slow(request: httpx.Request) -> httpx.Response:
        calls.append("read")
        raise httpx.ReadTimeout("slow", request=request)

    recovered = await turnstile(flaky).passed("token", "203.0.113.7")
    timed_out = await turnstile(slow).passed("token", "203.0.113.7")

    assert recovered
    assert not timed_out
    assert calls == ["connect", "connect", "read"]


async def test_without_a_secret_the_check_is_off() -> None:
    assert await CaptchaOff().passed(None, "203.0.113.7")
