"""The events workspaces publishes (workspaces plan §3.2); ids, codes and times only (§12).

Consumers: tasks unassign and clear projects, knowledge rescopes its index, meetings,
agent and proactive follow access, billing follows seats, alerting reports deletions.
"""

from datetime import datetime
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from shosai.core.events.domain_event import DomainEvent, EventCode
from shosai.features.workspaces.domain.access import AccessLevel
from shosai.features.workspaces.domain.memberships import RemovalReason
from shosai.features.workspaces.domain.roles import WorkspaceRole


class JoinChannel(StrEnum):
    """How a person became a member."""

    CREATED = "created"
    INVITATION = "invitation"
    DOMAIN = "domain"


class SuspensionSource(StrEnum):
    """Who suspended a workspace; the admin's reason stays in the audit log."""

    PLATFORM = "platform"
    BILLING = "billing"


class WorkspaceCreated(DomainEvent):
    """A person created a workspace and owns it."""

    event_type: ClassVar[str] = "workspaces.workspace.created"
    version: ClassVar[int] = 1
    org_id: UUID
    owner_user_id: UUID


class WorkspaceSuspended(DomainEvent):
    """Every member lost access until the workspace is resumed; nothing was deleted."""

    event_type: ClassVar[str] = "workspaces.workspace.suspended"
    version: ClassVar[int] = 1
    org_id: UUID
    source: SuspensionSource


class WorkspaceResumed(DomainEvent):
    """A suspended workspace is open to its members again."""

    event_type: ClassVar[str] = "workspaces.workspace.resumed"
    version: ClassVar[int] = 1
    org_id: UUID


class WorkspaceDeletionScheduled(DomainEvent):
    """The owner deleted the workspace: hidden now, erased at `erase_at` unless cancelled."""

    event_type: ClassVar[str] = "workspaces.workspace.deletion_scheduled"
    version: ClassVar[int] = 1
    org_id: UUID
    erase_at: datetime


class WorkspaceDeletionCancelled(DomainEvent):
    """A scheduled deletion was cancelled; everything shows again as it was."""

    event_type: ClassVar[str] = "workspaces.workspace.deletion_cancelled"
    version: ClassVar[int] = 1
    org_id: UUID


class WorkspaceDeleted(DomainEvent):
    """Every slice erased the workspace's data; its id is retired."""

    event_type: ClassVar[str] = "workspaces.workspace.deleted"
    version: ClassVar[int] = 1
    org_id: UUID


class MemberJoined(DomainEvent):
    """A person became an active member."""

    event_type: ClassVar[str] = "workspaces.member.joined"
    version: ClassVar[int] = 1
    org_id: UUID
    user_id: UUID
    membership_id: UUID
    via: JoinChannel


class MemberRemoved(DomainEvent):
    """A membership ended; the person's workspace content passes to `successor_user_id`."""

    event_type: ClassVar[str] = "workspaces.member.removed"
    version: ClassVar[int] = 1
    org_id: UUID
    user_id: UUID
    membership_id: UUID
    reason: RemovalReason
    successor_user_id: UUID | None = None


class MemberRoleChanged(DomainEvent):
    """A member's role changed."""

    event_type: ClassVar[str] = "workspaces.member.role_changed"
    version: ClassVar[int] = 1
    org_id: UUID
    membership_id: UUID
    role: WorkspaceRole


class TeamDeleted(DomainEvent):
    """A team is gone; rows granted to it keep their other grantees."""

    event_type: ClassVar[str] = "workspaces.team.deleted"
    version: ClassVar[int] = 1
    org_id: UUID
    team_id: UUID


class ProjectDeleted(DomainEvent):
    """A project is gone; its meetings, tasks and files stay without it."""

    event_type: ClassVar[str] = "workspaces.project.deleted"
    version: ClassVar[int] = 1
    org_id: UUID
    project_id: UUID


class AccessChanged(DomainEvent):
    """A row's access changed; indexes refresh its payload, reads never wait for them."""

    event_type: ClassVar[str] = "workspaces.access.changed"
    version: ClassVar[int] = 1
    org_id: UUID
    resource_kind: EventCode
    resource_id: UUID
    level: AccessLevel


class MeetingShared(DomainEvent):
    """A member's recording is shared into a workspace, or its audience changed."""

    event_type: ClassVar[str] = "workspaces.meeting.shared"
    version: ClassVar[int] = 1
    org_id: UUID
    session_id: UUID
    level: AccessLevel


class MeetingUnshared(DomainEvent):
    """A recording left a workspace: stopped, withdrawn on leaving, or its owner hidden."""

    event_type: ClassVar[str] = "workspaces.meeting.unshared"
    version: ClassVar[int] = 1
    org_id: UUID
    session_id: UUID


class KnowledgeItemAdded(DomainEvent):
    """A file or a connected source became knowledge of a workspace."""

    event_type: ClassVar[str] = "workspaces.knowledge_item.added"
    version: ClassVar[int] = 1
    org_id: UUID
    item_id: UUID
    file_id: UUID | None = None


class KnowledgeItemRemoved(DomainEvent):
    """A knowledge item left a workspace."""

    event_type: ClassVar[str] = "workspaces.knowledge_item.removed"
    version: ClassVar[int] = 1
    org_id: UUID
    item_id: UUID
