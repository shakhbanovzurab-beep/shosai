"""`GET /v1/health` answers 200, is never cached and is the shell's only route."""

from fastapi import FastAPI
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry

from shosai.core.config.sections import WebSettings
from shosai.core.web.app import HttpTelemetry, build_http_app
from tests.composition.public_routes import route_snapshot
from tests.core.web.probe_app import client_of


def shell_app() -> FastAPI:
    """The shell alone, as a role without features builds it."""
    telemetry = HttpTelemetry(CollectorRegistry(), TracerProvider(shutdown_on_exit=False))
    return build_http_app(WebSettings(), telemetry)


async def test_health_answers_ok_and_is_never_cached() -> None:
    async with client_of(shell_app()) as client:
        response = await client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["Cache-Control"] == "no-store"


def test_the_shell_exposes_only_the_health_route() -> None:
    assert route_snapshot(shell_app()) == ["GET /v1/health"]
