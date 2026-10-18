"""The events files publishes (files plan §3.2): ids, sizes and codes, nothing personal.

Consumers: knowledge indexes a file Leo starts using and drops the vectors of one it stops
using or that is deleted; workspaces withdraws a deleted file's knowledge items.
"""

from typing import ClassVar
from uuid import UUID

from shosai.core.events.domain_event import DomainEvent, EventCode


class FileUploaded(DomainEvent):
    """A file joined a person's or a workspace's File Manager."""

    event_type: ClassVar[str] = "files.file.uploaded"
    version: ClassVar[int] = 1
    file_id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None
    size_bytes: int
    kind: EventCode


class FileDeleted(DomainEvent):
    """A file was deleted: hidden from everyone now, gone for good after 7 days."""

    event_type: ClassVar[str] = "files.file.deleted"
    version: ClassVar[int] = 1
    file_id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None


class FileRestored(DomainEvent):
    """Support brought a deleted file back within its 7 days; it is shared nowhere."""

    event_type: ClassVar[str] = "files.file.restored"
    version: ClassVar[int] = 1
    file_id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None


class LeoUseChanged(DomainEvent):
    """Leo started or stopped using a file."""

    event_type: ClassVar[str] = "files.leo_use.changed"
    version: ClassVar[int] = 1
    file_id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None
    used: bool
