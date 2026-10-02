"""The ops app of every long-running role: liveness, readiness and metrics (F1-C3, §16).

It listens on the internal ops port, which the edge never proxies, so dependency state
and metrics are never reachable from the internet. It has no request boundary, access
lines or spans: a probe every few seconds and a scrape every 15 s would only add noise.

- `GET /livez` answers 200 while the event loop runs the process; it checks nothing else,
  so a dependency outage never makes the orchestrator restart a healthy process.
- `GET /readyz` answers 200 while the process takes work and 503 while it starts or drains;
  the body names each dependency `ok` or `down` (`core/health/readiness.py`).
- `GET /metrics` exposes the process registry in the format the scraper asks for; the
  OpenMetrics format carries the exemplars that link a metric to a trace (§16.1).
"""

from typing import Literal

from fastapi import APIRouter, FastAPI, Request, Response
from prometheus_client import CollectorRegistry
from prometheus_client.exposition import choose_encoder
from pydantic import BaseModel, ConfigDict

from whisperer.core.health.readiness import Readiness, ReadinessReport

OPS_TITLE = "Whisperer ops"
NOT_READY_STATUS = 503


class Liveness(BaseModel):
    """The process runs its event loop."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]


def build_ops_app(readiness: Readiness, registry: CollectorRegistry) -> FastAPI:
    """The ops app of one process; no docs, no schema, nothing a user could reach."""
    app = FastAPI(title=OPS_TITLE, docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(build_ops_router(readiness, registry))
    return app


def build_ops_router(readiness: Readiness, registry: CollectorRegistry) -> APIRouter:
    """The three ops routes over the process's readiness and metrics registry."""
    router = APIRouter()

    @router.get("/livez")
    async def livez() -> Liveness:
        """Answer while the event loop runs."""
        return Liveness(status="ok")

    @router.get("/readyz")
    async def readyz(response: Response) -> ReadinessReport:
        """200 while the process takes work, 503 while it starts or drains."""
        report = await readiness.report()
        if not report.ready:
            response.status_code = NOT_READY_STATUS
        return report

    # Синхронная функция: FastAPI выполняет её в пуле потоков, и сбор реестра — чтение
    # /proc и обход коллекторов — не занимает цикл событий.
    @router.get("/metrics")
    def metrics(request: Request) -> Response:
        """The registry in the exposition format the scraper accepts."""
        encoder, content_type = choose_encoder(request.headers.get("accept", ""))
        return Response(content=encoder(registry), media_type=content_type)

    return router
