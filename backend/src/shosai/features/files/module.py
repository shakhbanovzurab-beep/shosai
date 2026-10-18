"""The files slice as composition sees it (files plan §3.1).

Step 1 published the contract, the events and the domain; step 2 adds the tables, the
shareable `file` resource and the account data handler; step 3 the uploads straight to
the bucket, their claim by other slices and the sweep; step 4 the File Manager, downloads
through the edge, support's hidden files and their purge. The quota's 90 days and Leo's
use join in the later steps of the plan.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.files.application.account_data import ACCOUNT_DATA, FilesAccountData
from shosai.features.files.application.downloads import Downloads
from shosai.features.files.application.file_manager import FileManager
from shosai.features.files.application.folders import Folders
from shosai.features.files.application.hidden_files import HiddenFiles
from shosai.features.files.application.upload_claims import UploadClaims
from shosai.features.files.application.upload_links import StorageOfHomes
from shosai.features.files.application.upload_sweep import UploadSweep
from shosai.features.files.application.uploads import UploadService
from shosai.features.files.channels.http.admin_files import build_admin_files_router
from shosai.features.files.channels.http.files import build_files_router, build_folders_router
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
from shosai.features.files.settings import FilesSettings, downloads_through_edge


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Uploads, the File Manager, downloads, hidden files and the account data handler."""
    transactions, ports = services.transactions, services.ports
    base = services.settings.features.get(FilesSettings).files_download_base_url
    handler = FilesAccountData(transactions, (services.objects, services.uploads))
    deleter = ObjectDeleter(transactions, services.objects)
    storage = StorageOfHomes(services.objects, services.uploads)
    uploads = UploadService(transactions, storage, (ports, deleter))
    sweep = UploadSweep(transactions, (services.uploads, deleter))
    claims = UploadClaims()
    manager = FileManager(transactions, (ports, services.outbox, claims))
    downloads = Downloads(
        transactions, (services.objects, ports), None if base is None else str(base)
    )
    hidden = HiddenFiles(transactions, (services.outbox, deleter))
    yield FeatureParts(
        http_routers=(
            build_uploads_router(uploads, ports),
            build_files_router((manager, downloads), ports),
            build_folders_router(Folders(transactions), ports),
            build_admin_files_router(hidden, ports),
        ),
        task_handlers=task_handlers(sweep, hidden),
        periodic_jobs=PERIODIC_JOBS,
        provides=(ACCOUNT_DATA_HANDLERS.bind(handler), UPLOADS.bind(claims)),
    )


FILES = FeatureModule(
    name="files",
    build=build,
    settings=(FilesSettings,),
    production_checks=(downloads_through_edge,),
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
