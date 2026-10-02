"""The factory of a public HTTP app: the shell without features (target architecture §5).

Each role builds its app at start from its settings and telemetry; composition adds the
feature routers. Middlewares, outermost first:

1. `RequestBoundary` — request id, log context, common headers, access line, the HTTP
   metrics from the route the router matched, and the last-resort 500;
2. CORS — only for the explicit allowlist, absent when the list is empty.

FastAPI's native tracing wraps all of them, so every log line of a request carries its
`trace_id`. Proxy trust is the server's job: uvicorn rewrites the client address and the
scheme from `X-Forwarded-*` only for `forwarded_allow_ips`, before the app sees the scope.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from importlib.metadata import version

from fastapi import APIRouter, FastAPI
from fastapi.telemetry import TelemetryConfig
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CollectorRegistry
from starlette.middleware.cors import CORSMiddleware

from whisperer.core.config.sections import WebSettings
from whisperer.core.web.boundary import RequestBoundary
from whisperer.core.web.envelope import ERROR_RESPONSES
from whisperer.core.web.error_handlers import install_error_handlers
from whisperer.core.web.health import build_health_router
from whisperer.core.web.http_metrics import HttpMetrics
from whisperer.core.web.request_ids import REQUEST_ID_HEADER
from whisperer.core.web.route_templates import RouteTemplates

API_TITLE = "Whisperer API"
CORS_MAX_AGE_SECONDS = 600


@dataclass(frozen=True, slots=True)
class HttpTelemetry:
    """Where an app reports: the process metrics registry and tracer provider."""

    registry: CollectorRegistry
    tracer_provider: TracerProvider


def build_http_app(
    web: WebSettings, telemetry: HttpTelemetry, routers: Sequence[APIRouter] = ()
) -> FastAPI:
    """A public app with the health route and the given feature routers."""
    docs = web.api_docs_enabled
    app = FastAPI(
        title=API_TITLE,
        version=version("whisperer"),
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
        responses=ERROR_RESPONSES,
        telemetry=native_tracing(telemetry.tracer_provider),
    )
    install_error_handlers(app)
    app.include_router(build_health_router())
    for router in routers:
        app.include_router(router)
    # Шаблоны маршрутов собираются до первого запроса; неоднозначность останавливает старт.
    templates = RouteTemplates(app)
    # Starlette оборачивает в порядке добавления: добавленный последним — самый внешний.
    if web.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(web.cors_allowed_origins),
            # Вход и обновление сессии в кабинете идут через cookie.
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[REQUEST_ID_HEADER],
            max_age=CORS_MAX_AGE_SECONDS,
        )
    app.add_middleware(
        RequestBoundary, metrics=HttpMetrics(telemetry.registry), templates=templates
    )
    return app


def native_tracing(provider: TracerProvider) -> TelemetryConfig:
    """FastAPI's server spans into the process provider; metrics and logs have their own way.

    Metrics come from the request boundary and logs from structlog (§16.1). Spans of
    dependencies, endpoints and serialization are off: one server span per request keeps
    the volume within §16.7, and database and client spans show where the time went.
    """
    return {
        "tracer_provider": provider,
        "tracing": True,
        "metrics": False,
        "logs": False,
        "operation_spans": False,
        "auto_configure": False,
    }


def forwarded_allow_ips(web: WebSettings) -> list[str]:
    """Proxies uvicorn trusts for `X-Forwarded-For` and `-Proto`; an empty list trusts none."""
    return [str(network) for network in web.trusted_proxy_addresses]
