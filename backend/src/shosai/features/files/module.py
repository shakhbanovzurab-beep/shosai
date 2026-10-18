"""The files slice as composition sees it (files plan §3.1), step by step:

- 1: the contract, the events and the domain;
- 2: the tables, the shareable `file` resource and the account data handler;
- 3: uploads straight to the bucket, their claim by other slices and the sweep;
- 4: the File Manager, downloads through the edge, support's hidden files and the purge;
- 5: the quota's 90 days, its reminders and the inv-11 reconciliation;
- 6a and 6b: Leo's use within the knowledge limit, reindex, and FL-D10's 90 days;
- 7: identity's deletion window and support's audited file actions;
- 9: the `FileReader` port and Leo's `files` toolset.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.core.idempotency.action_items import ActionItems
from shosai.features.files.application.account_data import ACCOUNT_DATA, FilesAccountData
from shosai.features.files.application.downloads import Downloads
from shosai.features.files.application.file_edits import FileEdits
from shosai.features.files.application.file_manager import FileManager
from shosai.features.files.application.file_reader import FilesReader
from shosai.features.files.application.folders import Folders
from shosai.features.files.application.hidden_files import HiddenFiles
from shosai.features.files.application.leo_sweep import LeoSweep
from shosai.features.files.application.leo_use import LeoUse
from shosai.features.files.application.leo_watch import LeoWatch
from shosai.features.files.application.quota_reconciliation import QuotaReconciliation
from shosai.features.files.application.quota_sweep import QuotaSweep
from shosai.features.files.application.quota_watch import QuotaWatch
from shosai.features.files.application.support_files import SupportFiles
from shosai.features.files.application.upload_claims import UploadClaims
from shosai.features.files.application.upload_links import StorageOfHomes
from shosai.features.files.application.upload_sweep import UploadSweep
from shosai.features.files.application.uploads import UploadService
from shosai.features.files.channels.agent_tool_reads import FileReads
from shosai.features.files.channels.agent_tool_writes import FileWrites
from shosai.features.files.channels.agent_tools import FILES_TOOLS
from shosai.features.files.channels.http.admin_files import build_admin_files_router
from shosai.features.files.channels.http.files import build_files_router, build_folders_router
from shosai.features.files.channels.http.storage import build_storage_router
from shosai.features.files.channels.http.uploads import build_uploads_router
from shosai.features.files.channels.subscriptions import subscriptions
from shosai.features.files.channels.tasks import PERIODIC_JOBS, FilesJobs, task_handlers
from shosai.features.files.contracts import FILE_READER, UPLOADS
from shosai.features.files.contracts.events import (
    FileDeleted,
    FileRestored,
    FileUploaded,
    LeoReindexRequested,
    LeoUseChanged,
)
from shosai.features.files.emails.leo_over_limit import LEO_OVER_LIMIT
from shosai.features.files.emails.storage_over_limit import STORAGE_OVER_LIMIT
from shosai.features.files.infrastructure.file_records import (
    FILE_RESOURCE,
    FileFolderRecord,
    StorageFileRecord,
)
from shosai.features.files.infrastructure.object_deleter import ObjectDeleter
from shosai.features.files.infrastructure.quota_metrics import QuotaMetrics
from shosai.features.files.infrastructure.upload_records import (
    ObjectDeletionRecord,
    StorageUsageRecord,
    UploadRecord,
)
from shosai.features.files.objectives import FILES_MONITORS
from shosai.features.files.settings import FilesSettings, downloads_through_edge


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Uploads, the File Manager with Leo's use, downloads, hidden files, the quota and the
    account data."""
    transactions, ports = services.transactions, services.ports
    base = services.settings.features.get(FilesSettings).files_download_base_url
    deleter = ObjectDeleter(transactions, services.objects)
    storage = StorageOfHomes(services.objects, services.uploads)
    claims = UploadClaims()
    metrics = QuotaMetrics(services.registry)
    watch = QuotaWatch(transactions, (ports, services.outbox, services.email, metrics))
    leo = LeoUse(ports, services.outbox)
    leo_watch = LeoWatch(transactions, (ports, leo, services.email, metrics))
    hidden = HiddenFiles(transactions, deleter)
    support = SupportFiles(transactions, (ports, services.outbox, watch, leo, leo_watch))
    downloads = Downloads(
        transactions, (services.objects, ports), None if base is None else str(base)
    )
    jobs = FilesJobs(
        uploads=UploadSweep(transactions, (services.uploads, deleter)),
        hidden=hidden,
        quota=QuotaSweep(transactions, watch),
        leo=LeoSweep(transactions, leo_watch),
        reconciliation=QuotaReconciliation(transactions, (services.objects, metrics)),
    )
    handler = FilesAccountData(transactions, (services.objects, services.uploads))
    edits = FileEdits(ports, services.outbox, leo)
    manager = FileManager(transactions, (ports, services.outbox, claims, leo, edits))
    folders = Folders(transactions, (ports, leo))
    reader = FilesReader(transactions, (ports, services.objects))
    items = ActionItems(services.effects, services.outbox)
    tools = (
        *FileReads(transactions, (ports, reader)).bound(),
        *FileWrites(transactions, (edits, folders, leo, items)).bound(),
    )
    yield FeatureParts(
        http_routers=(
            build_uploads_router(UploadService(transactions, storage, (ports, deleter)), ports),
            build_files_router((manager, downloads), ports),
            build_folders_router(folders, ports),
            build_storage_router((watch, leo_watch), ports),
            build_admin_files_router(support, ports),
        ),
        task_handlers=task_handlers(jobs),
        periodic_jobs=PERIODIC_JOBS,
        subscriptions=subscriptions((watch, leo_watch)),
        email_templates=(STORAGE_OVER_LIMIT, LEO_OVER_LIMIT),
        agent_tools=tools,
        provides=(
            ACCOUNT_DATA_HANDLERS.bind(handler),
            UPLOADS.bind(claims),
            FILE_READER.bind(reader),
        ),
    )


FILES = FeatureModule(
    name="files",
    build=build,
    settings=(FilesSettings,),
    production_checks=(downloads_through_edge,),
    account_data=(ACCOUNT_DATA,),
    monitors=FILES_MONITORS,
    shareable=(FILE_RESOURCE,),
    agent_tools=FILES_TOOLS,
    models=(
        FileFolderRecord,
        StorageFileRecord,
        UploadRecord,
        StorageUsageRecord,
        ObjectDeletionRecord,
    ),
    events=(FileUploaded, FileDeleted, FileRestored, LeoUseChanged, LeoReindexRequested),
)
