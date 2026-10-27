"""The slice's task: Jev's zero-retention check, once a day (ADR 0069 DL-D1, plan §1.4).

The task reads OpenRouter's zero-data-retention list and the pinned model's endpoints and
keeps the answer for three days. A read that fails keeps the last answer: three failed days
in a row let it expire, and the points run their rules until a read succeeds again.
"""

from datetime import timedelta
from typing import Final

import httpx
import structlog

from shosai.core.ai.adapters.openrouter_endpoints import zero_retention
from shosai.core.kernel.homes import Home
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.decisions.infrastructure.provider_terms import ProviderTerms

CHECK_ZERO_RETENTION: Final = TaskDeclaration(
    name="decisions.check_zero_retention",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=2),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PERIODIC_JOBS: Final = (
    PeriodicJob(CHECK_ZERO_RETENTION, every=timedelta(days=1), homes=(Home.EU,)),
)
log = structlog.stdlib.get_logger(__name__)


def zero_retention_check(
    client: httpx.AsyncClient, terms: ProviderTerms, model: str
) -> TaskHandler[HomeTaskPayload]:
    """The daily check bound to the process's HTTP client."""

    async def check(_payload: HomeTaskPayload) -> None:
        try:
            keeps_nothing = await zero_retention(client, model)
        except httpx.HTTPError as error:
            log.warning(
                "Список нулевого хранения OpenRouter не прочитан", error=type(error).__name__
            )
            return
        await terms.record(keeps_nothing=keeps_nothing)
        if keeps_nothing:
            log.info("Эндпоинты Jev в списке нулевого хранения", model=model)
        else:
            log.error("Эндпоинт Jev вне списка нулевого хранения: решают правила", model=model)

    return TaskHandler(CHECK_ZERO_RETENTION, check)
