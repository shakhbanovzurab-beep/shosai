"""Invitations, grants and share records (workspaces plan §3.4; revision `c41d7e9a2b85`).

An invitation keeps only the SHA-256 of its link's secret. A grant names a member or a
team for a `selected` row. A share record brings a member's own meeting or file into a
workspace without copying it (§7).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Text,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.workspaces.infrastructure.organization_records import (
    member_reference,
    org_reference,
)

SHARED_ACCESS = "access IN ('selected', 'organization')"


class Invitation(ModelBase):
    """A pending invitation: one-time, bound to an address, 14 days (ADR 0053 point 3)."""

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("length(email) BETWEEN 3 AND 254", name="email_length"),
        CheckConstraint("role IN ('admin', 'member')", name="role_known"),
        CheckConstraint("length(token_sha256) = 32", name="token_digest_length"),
        CheckConstraint("expires_at > sent_at", name="expires_after_sent"),
        CheckConstraint(
            "(accepted_at IS NULL) = (accepted_membership_id IS NULL)",
            name="accepted_with_membership",
        ),
        Index("uq_invitations_token_sha256", "token_sha256", unique=True),
        Index(
            "uq_invitations_pending_email",
            "org_id",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    org_id: Mapped[UUID] = org_reference()
    email: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    team_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid), server_default=text("'{}'::uuid[]"))
    token_sha256: Mapped[bytes] = mapped_column(LargeBinary)
    invited_by_membership_id: Mapped[UUID | None] = member_reference("SET NULL")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_membership_id: Mapped[UUID | None] = member_reference("SET NULL")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResourceGrant(ModelBase):
    """One member or team a `selected` row of a workspace is granted to (§7)."""

    __tablename__ = "resource_grants"
    __table_args__ = (
        CheckConstraint("resource_kind ~ '^[a-z][a-z0-9_]{0,31}$'", name="resource_kind_form"),
        CheckConstraint("grantee_kind IN ('member', 'team')", name="grantee_kind_known"),
        Index("ix_resource_grants_resource", "resource_kind", "resource_id"),
        Index("ix_resource_grants_grantee", "grantee_kind", "grantee_id"),
    )

    org_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    resource_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    grantee_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    grantee_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkspaceMeetingShare(ModelBase):
    """A member's recording shared into one workspace at a time, with its audience."""

    __tablename__ = "workspace_meeting_shares"
    __table_args__ = (
        CheckConstraint(SHARED_ACCESS, name="access_known"),
        Index("ix_workspace_meeting_shares_org", "org_id", "shared_at"),
    )

    # Встреча среза meetings: без внешнего ключа между срезами.
    session_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    org_id: Mapped[UUID] = org_reference()
    shared_by_membership_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("memberships.id", ondelete="CASCADE")
    )
    access: Mapped[str] = mapped_column(Text)
    transcript_shared: Mapped[bool] = mapped_column(Boolean, server_default=false())
    project_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="SET NULL")
    )
    shared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkspaceKnowledgeItem(ModelBase):
    """A file or a connected source a workspace knows: an upload, a member's file, a source."""

    __tablename__ = "workspace_knowledge_items"
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('upload', 'personal', 'connector')", name="source_kind_known"
        ),
        CheckConstraint(
            "(source_kind = 'connector') = (connector_source_id IS NOT NULL) "
            "AND (source_kind = 'connector') = (file_id IS NULL)",
            name="source_matches_kind",
        ),
        CheckConstraint(SHARED_ACCESS, name="access_known"),
        Index(
            "uq_workspace_knowledge_items_file",
            "org_id",
            "file_id",
            unique=True,
            postgresql_where=text("file_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    org_id: Mapped[UUID] = org_reference()
    source_kind: Mapped[str] = mapped_column(Text)
    # Файл среза files или источник среза connectors: без внешних ключей между срезами.
    file_id: Mapped[UUID | None] = mapped_column(Uuid)
    connector_source_id: Mapped[UUID | None] = mapped_column(Uuid)
    access: Mapped[str] = mapped_column(Text)
    project_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="SET NULL")
    )
    added_by_membership_id: Mapped[UUID | None] = member_reference("SET NULL")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
