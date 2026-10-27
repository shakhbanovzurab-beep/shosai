"""Studio's tasks: the catalogue's refresh from OpenRouter's list, once a day in the EU home.

The refresh is a tick: a run lost or repeated changes nothing the next one would not, since
each writes the list's description over the last one and reports a model only when it first
goes missing or first proposes another tier.
"""

from datetime import timedelta
from typing import Final

from shosai.core.kernel.homes import Home
from shosai.core.schedule.jobs import PeriodicJob
from shosai.core.tasks.declaration import NO_RETRY, TaskDeclaration, TaskHandler, TaskKind
from shosai.core.tasks.payloads import HomeTaskPayload
from shosai.core.tasks.queues import TaskQueue
from shosai.features.studio.application.catalogue_refresh import CatalogueRefresh

REFRESH_CATALOGUE: Final = TaskDeclaration(
    name="studio.refresh_catalogue",
    queue=TaskQueue.DEFAULT,
    payload=HomeTaskPayload,
    deadline=timedelta(minutes=5),
    retry=NO_RETRY,
    kind=TaskKind.TICK,
)
PERIODIC_JOBS: Final = (PeriodicJob(REFRESH_CATALOGUE, timedelta(days=1), homes=(Home.EU,)),)


def refresh_tick(refresh: CatalogueRefresh) -> TaskHandler[HomeTaskPayload]:
    """The refresh, run by the EU home's tick."""

    async def run(_payload: HomeTaskPayload) -> None:
        await refresh.refresh()

    return TaskHandler(REFRESH_CATALOGUE, run)
