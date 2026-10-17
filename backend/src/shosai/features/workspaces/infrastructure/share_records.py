"""The records that bring a member's own resource into a workspace, by resource kind (§7).

A personal meeting is shared through `workspace_meeting_shares`, a personal file through
a `workspace_knowledge_items` row of source `personal`. Each record names the resource,
the workspace, the level, the member who shared it, and the key its grants are filed
under in `resource_grants`. Kinds without share records are read by their owner or
through their workspace only.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast

from sqlalchemy import Table

from shosai.features.workspaces.infrastructure.access_records import (
    WorkspaceKnowledgeItem,
    WorkspaceMeetingShare,
)

MEETING_KIND: Final = "meeting"
FILE_KIND: Final = "file"
KNOWLEDGE_ITEM_KIND: Final = "knowledge_item"


@dataclass(frozen=True, slots=True)
class ShareRecords:
    """Where one kind's share records live and what their columns are called."""

    table: Table
    resource: str
    org: str
    access: str
    sharer: str
    # Под каким видом и ключом записи гранты в resource_grants.
    grant_kind: str
    grant_key: str
    # Колонка и значение, отбирающие записи шаринга среди строк таблицы.
    only: tuple[str, str] | None = None


SHARE_RECORDS: Final[Mapping[str, ShareRecords]] = {
    MEETING_KIND: ShareRecords(
        table=cast("Table", WorkspaceMeetingShare.__table__),
        resource="session_id",
        org="org_id",
        access="access",
        sharer="shared_by_membership_id",
        grant_kind=MEETING_KIND,
        grant_key="session_id",
    ),
    FILE_KIND: ShareRecords(
        table=cast("Table", WorkspaceKnowledgeItem.__table__),
        resource="file_id",
        org="org_id",
        access="access",
        sharer="added_by_membership_id",
        grant_kind=KNOWLEDGE_ITEM_KIND,
        grant_key="id",
        only=("source_kind", "personal"),
    ),
}
