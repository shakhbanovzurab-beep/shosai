"""Building deletion for the process: the route, the saga, its sweeps and identity's handler."""

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureParts
from shosai.features.identity.application.account_erasure import IdentityAccountData
from shosai.features.identity.application.deletion import Deletions
from shosai.features.identity.application.erasure import Erasure
from shosai.features.identity.channels.deletion_tasks import (
    DELETION_JOBS,
    DUE_SOURCES,
    deletion_task_handlers,
)
from shosai.features.identity.channels.http.cookies import CookiePolicy
from shosai.features.identity.channels.http.deletion import build_deletion_router
from shosai.features.identity.channels.subscriptions import SUBSCRIPTIONS
from shosai.features.identity.emails.deletion_scheduled import DELETION_SCHEDULED
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.deletion_metrics import DeletionMetrics
from shosai.features.identity.infrastructure.directory import Directory


def deletion_parts(
    services: CoreServices, directory: Directory, markers: AccountMarkers, cookies: CookiePolicy
) -> FeatureParts:
    """What deletion adds to identity's parts."""
    deletions = Deletions(services.transactions, markers, services.outbox, services.email)
    erasure = Erasure(
        services.transactions, services.ports, services.outbox, DeletionMetrics(services.registry)
    )
    handler = IdentityAccountData(services.transactions, directory, services.objects)
    return FeatureParts(
        http_routers=(
            build_deletion_router(deletions, services.ports, services.rate_limiter, cookies),
        ),
        task_handlers=deletion_task_handlers(erasure, directory, services.tasks),
        subscriptions=SUBSCRIPTIONS,
        due_sources=DUE_SOURCES,
        periodic_jobs=DELETION_JOBS,
        email_templates=(DELETION_SCHEDULED,),
        provides=(ACCOUNT_DATA_HANDLERS.bind(handler),),
    )
