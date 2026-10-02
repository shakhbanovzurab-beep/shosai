"""The rate-limit dependency: 429 in the envelope with `Retry-After`, any subject, fail open."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from redis.asyncio import Redis

from tests.core.kv.outages import closed_port, redis_url
from whisperer.core.config.sections import WebSettings
from whisperer.core.kv.connection import connect_redis
from whisperer.core.kv.metrics import KeyValueMetrics
from whisperer.core.kv.rate_limits import RateLimit, RateLimiter
from whisperer.core.web.app import HttpTelemetry, build_http_app
from whisperer.core.web.rate_limit import rate_limited

SIGN_IN = RateLimit("sign_in", rate=5, period=timedelta(minutes=1), burst=2)


def user_subject(x_user: Annotated[str, Header()]) -> str:
    """A stand-in for the authenticated user a slice resolves from the token."""
    return f"user-{x_user}"


def limited_router(limiter: RateLimiter) -> APIRouter:
    router = APIRouter(prefix="/v1/probe")

    @router.post("/sign-in", dependencies=[Depends(rate_limited(limiter, SIGN_IN))])
    async def sign_in() -> dict[str, str]:
        return {"status": "ok"}

    @router.post(
        "/legacy",
        dependencies=[Depends(rate_limited(limiter, SIGN_IN, detail="Too many requests"))],
    )
    async def legacy() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/chat", dependencies=[Depends(rate_limited(limiter, SIGN_IN, user_subject))])
    async def chat() -> dict[str, str]:
        return {"status": "ok"}

    return router


@asynccontextmanager
async def limited_app(client: Redis) -> AsyncIterator[httpx.AsyncClient]:
    """The HTTP shell with the probe routes, limited through `client`."""
    limiter = RateLimiter(client, KeyValueMetrics(CollectorRegistry()))
    telemetry = HttpTelemetry(CollectorRegistry(), TracerProvider(shutdown_on_exit=False))
    app = build_http_app(WebSettings.model_validate({}), telemetry, [limited_router(limiter)])
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as http:
        yield http


async def test_over_the_limit_the_answer_is_429_with_retry_after(valkey: Redis) -> None:
    async with limited_app(valkey) as http:
        passed = [await http.post("/v1/probe/sign-in") for _ in range(2)]
        refused = await http.post("/v1/probe/sign-in")

    assert [response.status_code for response in passed] == [200, 200]
    assert refused.status_code == 429
    body = refused.json()
    assert body["error"]["code"] == "rate_limited"
    assert body["error"]["request_id"] == refused.headers["X-Request-ID"]
    assert body["detail"] == "rate_limited"
    seconds = body["error"]["params"]["retry_after_seconds"]
    assert refused.headers["Retry-After"] == str(seconds)
    assert 1 <= seconds <= 12


async def test_a_native_route_keeps_its_draft_detail(valkey: Redis) -> None:
    async with limited_app(valkey) as http:
        for _ in range(2):
            await http.post("/v1/probe/legacy")
        refused = await http.post("/v1/probe/legacy")

    assert refused.status_code == 429
    assert refused.json()["detail"] == "Too many requests"


async def test_the_subject_can_be_the_user_instead_of_the_address(valkey: Redis) -> None:
    async with limited_app(valkey) as http:
        for _ in range(2):
            await http.post("/v1/probe/chat", headers={"X-User": "7"})
        refused = await http.post("/v1/probe/chat", headers={"X-User": "7"})
        other = await http.post("/v1/probe/chat", headers={"X-User": "8"})

    assert (refused.status_code, other.status_code) == (429, 200)


async def test_without_valkey_requests_pass() -> None:
    client = connect_redis(redis_url(closed_port()), "whisperer-tests")
    async with limited_app(client) as http:
        responses = [await http.post("/v1/probe/sign-in") for _ in range(4)]
    await client.aclose()

    assert [response.status_code for response in responses] == [200] * 4
