"""Building transfers for the process: the saga, its tasks and the admin's routes."""

from shosai.core.features import CoreServices, FeatureParts
from shosai.features.identity.application.transfer_saga import SagaServices, TransferSaga
from shosai.features.identity.application.transfers import Transfers
from shosai.features.identity.channels.http.admin_transfers import build_admin_transfers_router
from shosai.features.identity.channels.transfer_tasks import (
    TRANSFER_JOBS,
    TRANSFER_SOURCES,
    transfer_task_handlers,
)
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.transfer_metrics import TransferMetrics
from shosai.features.identity.settings import IdentitySettings


def transfer_parts(
    services: CoreServices, directory: Directory, markers: AccountMarkers
) -> FeatureParts:
    """What transfers add to identity's parts."""
    allowed = services.settings.features.get(IdentitySettings).identity_transfers_allowed
    transfers = Transfers(services.transactions, directory, services.outbox, allowed=allowed)
    saga = TransferSaga(
        SagaServices(
            transactions=services.transactions, ports=services.ports, directory=directory,
            markers=markers, outbox=services.outbox,
            metrics=TransferMetrics(services.registry),
        )
    )  # fmt: skip
    return FeatureParts(
        http_routers=(build_admin_transfers_router(transfers, services.ports),),
        task_handlers=transfer_task_handlers(saga, services.transactions, services.tasks),
        due_sources=TRANSFER_SOURCES,
        periodic_jobs=TRANSFER_JOBS,
    )
