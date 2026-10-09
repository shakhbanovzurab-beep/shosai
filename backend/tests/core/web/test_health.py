"""`GET /v1/health` answers like the draft's and keeps the D1 contract of F1."""

from fastapi import FastAPI
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from shosai_contracts import Candidate, Scope, check, load_baseline, parse_routes, render_text
from shosai_contracts.jsonvalue import Json

from shosai.core.config.sections import WebSettings
from shosai.core.web.app import HttpTelemetry, build_http_app
from tests.composition.public_routes import route_snapshot
from tests.core.web.probe_app import client_of

F1_SCOPE = Scope(slices=frozenset({"F1"}))


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


def test_the_routes_of_f1_keep_the_draft_contract() -> None:
    app = shell_app()
    routes: list[Json] = list(route_snapshot(app))
    candidate = Candidate(openapi=app.openapi(), routes=parse_routes(routes, "shell"))

    report = check(load_baseline(), candidate, F1_SCOPE)

    assert report.is_compatible, render_text(report, F1_SCOPE)
