"""The files slice as composition sees it (files plan §3.1).

Step 1 published the contract, the events and the domain; step 2 adds the tables, the
shareable `file` resource and the account data handler; step 3 the uploads straight to
the bucket, their claim by other slices and the sweep. The File Manager and the quota join
in the later steps of the plan.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.files.application.account_data import ACCOUNT_DATA, FilesAccountData
from shosai.features.files.application.upload_claims import UploadClaims
from shosai.features.files.application.upload_links import StorageOfHomes
from shosai.features.files.application.upload_sweep import UploadSweep
from shosai.features.files.application.uploads import UploadService
from shosai.features.files.channels.http.uploads import build_uploads_router
from shosai.features.files.channels.tasks import PERIODIC_JOBS, task_handlers
from shosai.features.files.contracts import UPLOADS
from shosai.features.files.contracts.events import (
    FileDeleted,
    FileRestored,
    FileUploaded,
    LeoUseChanged,
)
from shosai.features.files.infrastructure.file_records import (
    FILE_RESOURCE,
    FileFolderRecord,
    StorageFileRecord,
)
from shosai.features.files.infrastructure.object_deleter import ObjectDeleter
from shosai.features.files.infrastructure.upload_records import (
    ObjectDeletionRecord,
    StorageUsageRecord,
    UploadRecord,
)


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Uploads, their claim and sweep, and the account data handler over both homes' buckets."""
    handler = FilesAccountData(services.transactions, (services.objects, services.uploads))
    deleter = ObjectDeleter(services.transactions, services.objects)
    storage = StorageOfHomes(services.objects, services.uploads)
    uploads = UploadService(services.transactions, storage, (services.ports, deleter))
    sweep = UploadSweep(services.transactions, (services.uploads, deleter))
    yield FeatureParts(
        http_routers=(build_uploads_router(uploads, services.ports),),
        task_handlers=task_handlers(sweep),
        periodic_jobs=PERIODIC_JOBS,
        provides=(ACCOUNT_DATA_HANDLERS.bind(handler), UPLOADS.bind(UploadClaims())),
    )


FILES = FeatureModule(
    name="files",
    build=build,
    account_data=(ACCOUNT_DATA,),
    shareable=(FILE_RESOURCE,),
    models=(
        FileFolderRecord,
        StorageFileRecord,
        UploadRecord,
        StorageUsageRecord,
        ObjectDeletionRecord,
    ),
    events=(FileUploaded, FileDeleted, FileRestored, LeoUseChanged),
)
