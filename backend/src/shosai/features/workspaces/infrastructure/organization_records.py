"""Workspaces, memberships, teams and projects (workspaces plan §3.4; revision `c41d7e9a2b85`).

Every table lives in the workspace's home and carries company isolation; a membership
references the person's global user id without a foreign key across slices (§5).
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
    false,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

ROLES = "'owner', 'admin', 'member', 'guest'"
REMOVAL_REASONS = "'removed_by_admin', 'left', 'account_erased', 'workspace_deleted'"
TEAM_COLORS = "'blue', 'green', 'amber', 'violet', 'rose', 'sky'"


def org_reference() -> Mapped[UUID]:
    """The company of a row; deleting the workspace removes it."""
    return mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"))


def member_reference(ondelete: str) -> Mapped[UUID | None]:
    """An optional membership a row names."""
    return mapped_column(Uuid, ForeignKey("memberships.id", ondelete=ondelete))


class Organization(ModelBase):
    """A workspace: its name, slug, state and sharing defaults; seats are billing's."""

    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 60", name="name_length"),
        CheckConstraint(
            "slug ~ '^[^-/[:space:]]([^/[:space:]]{0,38}[^-/[:space:]])?$'", name="slug_form"
        ),
        CheckConstraint("slug <> 'new'", name="slug_not_reserved"),
        CheckConstraint(
            "state IN ('active', 'suspended', 'deletion_scheduled')", name="state_known"
        ),
        CheckConstraint(
            "sharing_default IN ('private', 'participants', 'workspace')",
            name="sharing_default_known",
        ),
        CheckConstraint(
            "(state = 'suspended') = (suspended_at IS NOT NULL)", name="suspended_when_suspended"
        ),
        CheckConstraint(
            "suspension_reason IS NULL OR length(suspension_reason) BETWEEN 3 AND 300",
            name="suspension_reason_length",
        ),
        CheckConstraint(
            "(state = 'deletion_scheduled') = (erase_at IS NOT NULL)",
            name="erase_at_when_scheduled",
        ),
        CheckConstraint(
            "join_domain IS NULL OR length(join_domain) BETWEEN 3 AND 253",
            name="join_domain_length",
        ),
        Index("uq_organizations_slug", "slug", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="active")
    sharing_default: Mapped[str] = mapped_column(Text, server_default="participants")
    share_transcripts: Mapped[bool] = mapped_column(Boolean, server_default=false())
    members_can_invite: Mapped[bool] = mapped_column(Boolean, server_default=true())
    sharing_reviewed: Mapped[bool] = mapped_column(Boolean, server_default=false())
    join_domain: Mapped[str | None] = mapped_column(Text)
    suspension_reason: Mapped[str | None] = mapped_column(Text)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erase_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Согласие компании как оператора данных (nfr-14): пусто до первого договора (ADR 0053 п. 6).
    operator_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(ModelBase):
    """A person in a workspace with a role; kept as `removed` after it ends (§8.1)."""

    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(f"role IN ({ROLES})", name="role_known"),
        CheckConstraint("state IN ('active', 'hidden', 'removed')", name="state_known"),
        CheckConstraint(
            f"removal_reason IS NULL OR removal_reason IN ({REMOVAL_REASONS})",
            name="removal_reason_known",
        ),
        CheckConstraint(
            "(state = 'removed') = (removed_at IS NOT NULL AND removal_reason IS NOT NULL)",
            name="removed_when_removed",
        ),
        CheckConstraint("title IS NULL OR length(title) BETWEEN 1 AND 80", name="title_length"),
        Index("uq_memberships_org_user", "org_id", "user_id", unique=True),
        Index("ix_memberships_active_user", "user_id", postgresql_where=text("state = 'active'")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    org_id: Mapped[UUID] = org_reference()
    user_id: Mapped[UUID] = mapped_column(Uuid)
    role: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="active")
    title: Mapped[str | None] = mapped_column(Text)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str | None] = mapped_column(Text)
    # Раз в день при открытии пространства (план §3.6, поток 8).
    last_active_on: Mapped[date | None] = mapped_column(Date)
    # Время последнего применённого события аккаунта: старое событие не перекрывает новое.
    account_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Team(ModelBase):
    """A group of members; a private team shows only to its members and admins."""

    __tablename__ = "teams"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 40", name="name_length"),
        CheckConstraint("length(description) <= 140", name="description_length"),
        CheckConstraint(f"color IN ({TEAM_COLORS})", name="color_known"),
        Index("ix_teams_org_id", "org_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    org_id: Mapped[UUID] = org_reference()
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    color: Mapped[str] = mapped_column(Text)
    private: Mapped[bool] = mapped_column(Boolean, server_default=false())
    lead_membership_id: Mapped[UUID | None] = member_reference("SET NULL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TeamMember(ModelBase):
    """A member of a team; the company column lets row-level security guard it."""

    __tablename__ = "team_members"
    __table_args__ = (Index("ix_team_members_membership_id", "membership_id"),)

    team_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    membership_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("memberships.id", ondelete="CASCADE"), primary_key=True
    )
    org_id: Mapped[UUID] = org_reference()


class Project(ModelBase):
    """The shared context of a piece of work: its meetings, tasks, decisions and files."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 60", name="name_length"),
        CheckConstraint("length(description) <= 400", name="description_length"),
        CheckConstraint(
            "status IN ('planned', 'active', 'paused', 'completed')", name="status_known"
        ),
        Index("ix_projects_org_id", "org_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    org_id: Mapped[UUID] = org_reference()
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(Text, server_default="planned")
    lead_membership_id: Mapped[UUID | None] = member_reference("SET NULL")
    team_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("teams.id", ondelete="SET NULL"))
    target_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
