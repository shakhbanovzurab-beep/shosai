"""A public app with probe routes for every error path, its metrics and its spans in memory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry
from pydantic import BaseModel, Field

from whisperer.core.config.sections import WebSettings
from whisperer.core.kernel.errors import AppError
from whisperer.core.observability.span_privacy import PrivateAttributesSampler
from whisperer.core.web.app import HttpTelemetry, build_http_app

ITEM_ROUTE = "/v1/probe/items/{item_id}"
SECRET = "s3cr3t-value-from-the-request"
log = structlog.stdlib.get_logger("tests.probe")


class Credentials(BaseModel):
    """A body with a field that must never come back in an error."""

    email: str = Field(max_length=5)
    password: str = Field(min_length=64)


async def guarded_resource() -> AsyncIterator[str]:
    """A dependency with `yield`, like a guard that releases a slot after the response."""
    yield "slot"


GuardedResource = Annotated[str, Depends(guarded_resource)]


def probe_router() -> APIRouter:
    """Routes that answer normally or fail along each error path."""
    router = APIRouter(prefix="/v1/probe")
    add_domain_routes(router)
    add_framework_routes(router)
    return router


def add_domain_routes(router: APIRouter) -> None:
    """A normal route and the routes raising domain errors."""

    @router.get("/items/{item_id}")
    async def read_item(item_id: int, q: str | None = None) -> dict[str, int]:
        """A route with a template and a query."""
        log.info("Предмет прочитан", has_query=q is not None)
        return {"id": item_id}

    @router.get("/domain-error")
    async def domain_error() -> None:
        """A domain error with params."""
        raise AppError("item_locked", HTTPStatus.CONFLICT, params={"item_id": 7, "until": "x1"})

    @router.get("/native-detail")
    async def native_detail() -> None:
        """A domain error on a route whose draft contract has an object `detail`."""
        raise AppError("quota_exceeded", HTTPStatus.PAYMENT_REQUIRED, detail={"code": "quota"})

    @router.get("/rate-limited")
    async def rate_limited() -> None:
        """A rate limit with a fractional wait."""
        raise AppError(
            "rate_limited", HTTPStatus.TOO_MANY_REQUESTS, params={"retry_after_seconds": 2.2}
        )

    @router.get("/unavailable")
    async def unavailable() -> None:
        """A handled server error."""
        raise AppError("service_unavailable", HTTPStatus.SERVICE_UNAVAILABLE)


def add_framework_routes(router: APIRouter) -> None:
    """Routes failing with HTTP exceptions, validation and an unhandled exception."""

    @router.get("/http-code")
    async def http_code() -> None:
        """An HTTP exception whose detail is a code, with a challenge header."""
        raise HTTPException(401, "token_expired", headers={"WWW-Authenticate": "Bearer"})

    @router.get("/http-sentence")
    async def http_sentence() -> None:
        """An HTTP exception whose detail is a sentence that must not reach the client."""
        raise HTTPException(403, f"Пользователь {SECRET} не может войти")

    @router.get("/under-yield-dependency")
    async def under_yield_dependency(_resource: GuardedResource) -> None:
        """An HTTP exception below a dependency with `yield`; the draft answered it with 500."""
        raise HTTPException(422, "mindmap_unavailable")

    @router.post("/credentials")
    async def submit(credentials: Credentials) -> dict[str, str]:
        """A body validated by Pydantic."""
        return {"email": credentials.email}

    @router.get("/crash")
    async def crash() -> None:
        """An exception no handler takes."""
        message = f"сбой с {SECRET}"
        raise RuntimeError(message)


@dataclass(frozen=True, slots=True)
class ProbeApp:
    """The app under test and where its telemetry lands."""

    app: FastAPI
    registry: CollectorRegistry
    spans: InMemorySpanExporter

    def finished_spans(self) -> tuple[ReadableSpan, ...]:
        """Spans ended so far."""
        return self.spans.get_finished_spans()


def build_probe_app(web: WebSettings | None = None) -> ProbeApp:
    """The probe routes inside the real shell, with telemetry kept in memory."""
    registry = CollectorRegistry()
    spans = InMemorySpanExporter()
    provider = TracerProvider(sampler=PrivateAttributesSampler(), shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(spans))
    app = build_http_app(
        web or WebSettings(), HttpTelemetry(registry, provider), routers=[probe_router()]
    )
    return ProbeApp(app, registry, spans)


@asynccontextmanager
async def client_of(
    app: FastAPI, base_url: str = "http://testserver"
) -> AsyncIterator[httpx.AsyncClient]:
    """An HTTP client calling the app in-process."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=base_url) as client:
        yield client
