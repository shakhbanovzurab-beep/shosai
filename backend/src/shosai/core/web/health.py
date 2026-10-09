"""`GET /v1/health`: the public connectivity probe (D1, the web client reads `res.ok`).

It answers for the process only. Dependency state is reported by the readiness probe on
the internal ops port, never through the edge (F1 plan, F1-C3).
"""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict


class HealthStatus(BaseModel):
    """The process answers HTTP requests."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]


def build_health_router() -> APIRouter:
    """The router of the public health route; every public app includes it."""
    router = APIRouter(prefix="/v1", tags=["health"])

    # Имя функции даёт operationId `health_check_v1_health_get`, тот же, что у черновика.
    @router.get("/health", summary="Connectivity probe")
    async def health_check(response: Response) -> HealthStatus:
        """Answer 200 while the process serves HTTP; dependencies are not checked."""
        # Проба связности: ни браузер, ни прокси не должны отвечать за процесс из кэша.
        response.headers["Cache-Control"] = "no-store"
        return HealthStatus(status="ok")

    return router
