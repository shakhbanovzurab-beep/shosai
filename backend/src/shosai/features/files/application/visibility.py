"""Which files a person sees: the access policy inside files' own query (inv-14).

A file is visible when workspaces' policy admits it for the viewer and it is not hidden
by a deletion (FL-D5). Every list, search and Leo read of files starts from here.
"""

from sqlalchemy import Select, select

from shosai.features.files.infrastructure.file_records import FILE_RESOURCE, StorageFileRecord
from shosai.features.workspaces.contracts import AccessPolicy, Viewer


def visible_files(policy: AccessPolicy, viewer: Viewer) -> Select[StorageFileRecord]:
    """The files the viewer may see now."""
    return select(StorageFileRecord).where(
        policy.readable(FILE_RESOURCE, viewer), StorageFileRecord.deleted_at.is_(None)
    )
