"""What the workspace audit log records (nfr-17, inv-17; the admin screen's event kinds).

Every administrative action and access change writes one row in the action's own
transaction. A row names its action from this closed set, the acting member (none for
the platform's admin), and the target by kind and id; names and addresses are read from
their owners when the log is shown, never copied into it.
"""

from enum import StrEnum


class AuditAction(StrEnum):
    """An administrative action or access change inside a workspace."""

    WORKSPACE_CREATED = "workspace_created"
    MEMBER_INVITED = "member_invited"
    INVITATION_REVOKED = "invitation_revoked"
    MEMBER_JOINED = "member_joined"
    ROLE_CHANGED = "role_changed"
    MEMBER_REMOVED = "member_removed"
    MEMBER_LEFT = "member_left"
    SETTINGS_CHANGED = "settings_changed"
    DOMAIN_VERIFIED = "domain_verified"
    TEAM_CREATED = "team_created"
    TEAM_CHANGED = "team_changed"
    TEAM_DELETED = "team_deleted"
    PROJECT_CREATED = "project_created"
    PROJECT_CHANGED = "project_changed"
    PROJECT_DELETED = "project_deleted"
    ACCESS_CHANGED = "access_changed"
    FILE_TRANSFERRED = "file_transferred"
    SEATS_CHANGED = "seats_changed"
    OWNER_TRANSFERRED = "owner_transferred"
    SUSPENDED = "suspended"
    RESUMED = "resumed"
    DELETION_SCHEDULED = "deletion_scheduled"
    DELETION_CANCELLED = "deletion_cancelled"
