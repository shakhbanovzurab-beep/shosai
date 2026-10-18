"""The files slice as composition sees it (files plan §3.1).

Step 1 published the contract, the events and the domain; step 2 adds the tables, the
shareable `file` resource and the account data handler. Uploads, the File Manager and the
quota join in the later steps of the plan.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shosai.core.account_data.handlers import ACCOUNT_DATA_HANDLERS
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.files.application.account_data import ACCOUNT_DATA, FilesAccountData
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
from shosai.features.files.infrastructure.upload_records import (
    ObjectDeletionRecord,
    StorageUsageRecord,
    UploadRecord,
)


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Bind the account data handler over both homes' buckets."""
    handler = FilesAccountData(services.transactions, (services.objects, services.uploads))
    yield FeatureParts(provides=(ACCOUNT_DATA_HANDLERS.bind(handler),))


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
