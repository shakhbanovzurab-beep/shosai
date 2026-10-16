"""The caller's home and id reach the HTTP metric, the access line and the span (§16.2, §16.7)."""

from typing import Annotated
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Request
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry

from shosai.core.config.sections import WebSettings
from shosai.core.kernel.homes import Home
from shosai.core.web.app import HttpTelemetry, build_http_app
from shosai.core.web.http_metrics import DURATION_METRIC
from shosai.core.web.request_facts import note_caller
from tests.core.observability.capture import captured_logs

USER_ID = uuid4()


async def eu_caller(request: Request) -> None:
    """A stand-in for the authentication dependency of identity."""
    note_caller(request, Home.EU, USER_ID)


def router() -> APIRouter:
    routes = APIRouter(prefix="/v1/facts")

    @routes.get("/mine")
    async def mine(_: Annotated[None, Depends(eu_caller)]) -> dict[str, str]:
        """A route for a signed-in person."""
        return {"ok": "yes"}

    @routes.get("/public")
    async def public() -> dict[str, str]:
        """A route for anyone."""
        return {"ok": "yes"}

    return routes


def homes_counted(registry: CollectorRegistry) -> dict[str, str]:
    return {
        sample.labels["http_route"]: sample.labels["home"]
        for family in registry.collect()
        if family.name == DURATION_METRIC
        for sample in family.samples
        if sample.name.endswith("_count")
    }


async def test_the_caller_reaches_the_metric_the_access_line_and_the_span() -> None:
    registry = CollectorRegistry()
    spans = InMemorySpanExporter()
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(spans))
    app = build_http_app(
        WebSettings.model_validate({}), HttpTelemetry(registry, provider), [router()]
    )
    with captured_logs() as logs:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://shosai.example"
        ) as client:
            await client.get("/v1/facts/mine")
            await client.get("/v1/facts/public")

    assert homes_counted(registry) == {"/v1/facts/mine": "eu", "/v1/facts/public": ""}
    access = {line["route"]: line for line in logs.lines() if "route" in line}
    assert (access["/v1/facts/mine"]["home"], access["/v1/facts/mine"]["user_id"]) == (
        "eu",
        str(USER_ID),
    )
    assert "home" not in access["/v1/facts/public"]
    [mine] = [span for span in spans.get_finished_spans() if "mine" in span.name]
    attributes = dict(mine.attributes or {})
    assert (attributes["shosai.home"], attributes["user.id"]) == ("eu", str(USER_ID))
