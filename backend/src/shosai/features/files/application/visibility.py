"""Which files a person sees: the access policy inside files' own query (inv-14).

A file is visible when workspaces' policy admits it for the viewer, it is not hidden by a
deletion (FL-D5) and its owner's account is not in identity's deletion window (ADR 0045
point 6). Every list, search, download, Leo read and background read of files starts here.
"""

from sqlalchemy import Select, select

from shosai.features.files.infrastructure.file_records import FILE_RESOURCE, StorageFileRecord
from shosai.features.workspaces.contracts import AccessPolicy, Viewer


def visible_files(policy: AccessPolicy, viewer: Viewer) -> Select[StorageFileRecord]:
    """The files the viewer may see now."""
    return select(StorageFileRecord).where(
        policy.readable(FILE_RESOURCE, viewer),
        StorageFileRecord.deleted_at.is_(None),
        StorageFileRecord.account_hidden.is_(False),
    )
