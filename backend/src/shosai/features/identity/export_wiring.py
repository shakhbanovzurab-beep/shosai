"""Building export for the process: the routes, the runner, its sweeps and the mail."""

from shosai.core.features import CoreServices, FeatureParts
from shosai.features.identity.application.export_runner import ExportRunner
from shosai.features.identity.application.exports import Exports
from shosai.features.identity.channels.export_tasks import (
    EXPORT_JOBS,
    EXPORT_SOURCES,
    export_task_handlers,
)
from shosai.features.identity.channels.http.exports import build_export_router
from shosai.features.identity.emails.export_ready import EXPORT_READY


def export_parts(services: CoreServices) -> FeatureParts:
    """What export adds to identity's parts."""
    exports = Exports(services.transactions, services.objects)
    runner = ExportRunner(
        services.transactions, services.ports, (services.objects, services.uploads), services.email
    )
    return FeatureParts(
        http_routers=(build_export_router(exports, services.ports, services.rate_limiter),),
        task_handlers=export_task_handlers(runner, services.tasks),
        due_sources=EXPORT_SOURCES,
        periodic_jobs=EXPORT_JOBS,
        email_templates=(EXPORT_READY,),
    )
