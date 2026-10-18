"""Workspaces, memberships, teams, projects, invitations, grants, share records and audit (step 2).

Every table lives in the workspace's home (inv-15). Each table with a company column
carries company isolation (ADR 0053 point 1): a person reads the rows of the workspaces
they are an active member of — `app_member_org_ids()`, defined here — and writes only
into the transaction's workspace; the sweep role sees every row. A deferred constraint
trigger keeps a standing owner in every workspace. The audit log is monthly-partitioned,
kept 12 months, and the application may only insert and read it (inv-17).
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from shosai.core.db.database_roles import SWEEPER_ROLE
from shosai.core.db.migration_scope import (
    APPLICATION_WRITES,
    EVERY_HOME,
    MigrationScope,
    Privilege,
    disable_company_isolation,
    enable_company_isolation,
    grant_to_application,
    grant_to_sweeper,
    open_function,
    revoke_from_application,
    revoke_from_sweeper,
    runs_in,
)
from shosai.core.db.partitions.policy import (
    MonthlyPartitions,
    monthly_partition_range,
    register_monthly_partitions,
    unregister_monthly_partitions,
)

revision: str = "c41d7e9a2b85"
down_revision: str | None = "8bf7fd2e1bd6"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

AUDIT = MonthlyPartitions("org_audit_events", ahead_months=2, keep_months=12)
ROLES = "'owner', 'admin', 'member', 'guest'"
AUDIT_ACTIONS = (
    "'workspace_created', 'member_invited', 'invitation_revoked', 'member_joined', "
    "'role_changed', 'member_removed', 'member_left', 'settings_changed', 'domain_verified', "
    "'team_created', 'team_changed', 'team_deleted', 'project_created', 'project_changed', "
    "'project_deleted', 'access_changed', 'file_transferred', 'seats_changed', "
    "'owner_transferred', 'suspended', 'resumed', 'deletion_scheduled', 'deletion_cancelled'"
)
CODE_FORM = "'^[a-z0-9_.:-]{1,64}$'"
# Права роли приложения. Членства не удаляются (§8.1), журнал только дополняется (inv-17).
READ_WRITE: tuple[Privilege, ...] = ("SELECT", "INSERT", "UPDATE")
APPEND_ONLY: tuple[Privilege, ...] = ("SELECT", "INSERT")
ISOLATED_TABLES: dict[str, tuple[Privilege, ...]] = {
    "organizations": APPLICATION_WRITES,
    "memberships": READ_WRITE,
    "teams": APPLICATION_WRITES,
    "team_members": APPLICATION_WRITES,
    "projects": APPLICATION_WRITES,
    "invitations": APPLICATION_WRITES,
    "resource_grants": APPLICATION_WRITES,
    "workspace_meeting_shares": APPLICATION_WRITES,
    "workspace_knowledge_items": APPLICATION_WRITES,
    "org_audit_events": APPEND_ONLY,
}
MEMBER_ORGS_FUNCTION = """
CREATE FUNCTION app_member_org_ids() RETURNS uuid[]
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
  SELECT coalesce(array_agg(m.org_id), '{}'::uuid[])
  FROM public.memberships AS m
  WHERE m.user_id = public.app_user_id() AND m.state = 'active'
$$
"""
OWNER_FUNCTION = """
CREATE FUNCTION workspaces_keep_an_owner() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
  target uuid;
BEGIN
  IF TG_TABLE_NAME = 'organizations' THEN
    target := NEW.id;
  ELSIF TG_OP = 'DELETE' THEN
    target := OLD.org_id;
  ELSE
    target := NEW.org_id;
  END IF;
  IF EXISTS (SELECT 1 FROM public.organizations AS o WHERE o.id = target)
     AND NOT EXISTS (
       SELECT 1 FROM public.memberships AS m
       WHERE m.org_id = target AND m.role = 'owner' AND m.state IN ('active', 'hidden')
     ) THEN
    RAISE EXCEPTION 'workspace % has no owner', target
      USING ERRCODE = 'check_violation', CONSTRAINT = 'workspace_keeps_an_owner';
  END IF;
  RETURN NULL;
END
$$
"""
OWN_MEMBERSHIPS_POLICY = (
    "CREATE POLICY own_memberships ON memberships FOR SELECT "
    "USING (user_id = (SELECT app_user_id()))"
)
OWNER_TRIGGERS = (
    "CREATE CONSTRAINT TRIGGER organizations_keep_an_owner AFTER INSERT ON organizations "
    "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workspaces_keep_an_owner()",
    "CREATE CONSTRAINT TRIGGER memberships_keep_an_owner "
    "AFTER INSERT OR UPDATE OR DELETE ON memberships "
    "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workspaces_keep_an_owner()",
)


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str, *, default_now: bool = False, nullable: bool = False) -> sa.Column[datetime]:
    """A timestamp column with a time zone."""
    default = sa.func.now() if default_now else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


def org_column() -> sa.Column[UUID]:
    """The company of a row; its rows go with the workspace."""
    return sa.Column("org_id", sa.Uuid(), nullable=False)


def org_key(table: str) -> sa.ForeignKeyConstraint:
    """The company's foreign key: deleting the workspace removes its rows."""
    return sa.ForeignKeyConstraint(
        ["org_id"],
        ["organizations.id"],
        name=op.f(f"fk_{table}_org_id_organizations"),
        ondelete="CASCADE",
    )


def member_key(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    """A foreign key to a membership."""
    return sa.ForeignKeyConstraint(
        [column],
        ["memberships.id"],
        name=op.f(f"fk_{table}_{column}_memberships"),
        ondelete=ondelete,
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the workspace tables, their isolation, the owner rule and the audit log."""
    create_organizations()
    create_memberships()
    op.execute(MEMBER_ORGS_FUNCTION)
    open_function("app_member_org_ids", (), (scope.application_role, SWEEPER_ROLE))
    create_teams()
    create_projects()
    create_invitations()
    create_access_tables()
    create_audit()
    op.execute(OWNER_FUNCTION)
    for statement in OWNER_TRIGGERS:
        op.execute(statement)
    for table, privileges in ISOLATED_TABLES.items():
        # Компания самой строки organizations — её id.
        enable_company_isolation(table, column="id" if table == "organizations" else "org_id")
        grant_to_application(scope, table, privileges)
        grant_to_sweeper(table, ("SELECT",))
    # Свои членства человек читает в любом состоянии: экспорт, стирание, запрет переезда.
    op.execute(OWN_MEMBERSHIPS_POLICY)


def create_organizations() -> None:
    """The workspaces; seats are billing's, read through its port."""
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="active", nullable=False),
        sa.Column("sharing_default", sa.Text(), server_default="participants", nullable=False),
        sa.Column("share_transcripts", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("members_can_invite", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sharing_reviewed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("join_domain", sa.Text(), nullable=True),
        sa.Column("suspension_reason", sa.Text(), nullable=True),
        moment("suspended_at", nullable=True),
        moment("erase_at", nullable=True),
        moment("operator_consent_at", nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check("organizations", "length(name) BETWEEN 1 AND 60", "name_length"),
        # До 40 символов любой письменности, без пробелов, «/» и дефиса по краям.
        check(
            "organizations",
            "slug ~ '^[^-/[:space:]]([^/[:space:]]{0,38}[^-/[:space:]])?$'",
            "slug_form",
        ),
        check("organizations", "slug <> 'new'", "slug_not_reserved"),
        check(
            "organizations",
            "state IN ('active', 'suspended', 'deletion_scheduled')",
            "state_known",
        ),
        check(
            "organizations",
            "sharing_default IN ('private', 'participants', 'workspace')",
            "sharing_default_known",
        ),
        check(
            "organizations",
            "(state = 'suspended') = (suspended_at IS NOT NULL)",
            "suspended_when_suspended",
        ),
        check(
            "organizations",
            "suspension_reason IS NULL OR length(suspension_reason) BETWEEN 3 AND 300",
            "suspension_reason_length",
        ),
        check(
            "organizations",
            "(state = 'deletion_scheduled') = (erase_at IS NOT NULL)",
            "erase_at_when_scheduled",
        ),
        check(
            "organizations",
            "join_domain IS NULL OR length(join_domain) BETWEEN 3 AND 253",
            "join_domain_length",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.create_index("uq_organizations_slug", "organizations", ["slug"], unique=True)


def create_memberships() -> None:
    """A person in a workspace; the row stays after removal (§8.1)."""
    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        org_column(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="active", nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        moment("joined_at", default_now=True),
        moment("removed_at", nullable=True),
        sa.Column("removal_reason", sa.Text(), nullable=True),
        sa.Column("last_active_on", sa.Date(), nullable=True),
        check("memberships", f"role IN ({ROLES})", "role_known"),
        check("memberships", "state IN ('active', 'hidden', 'removed')", "state_known"),
        check(
            "memberships",
            "removal_reason IS NULL OR removal_reason IN "
            "('removed_by_admin', 'left', 'account_erased', 'workspace_deleted')",
            "removal_reason_known",
        ),
        check(
            "memberships",
            "(state = 'removed') = (removed_at IS NOT NULL AND removal_reason IS NOT NULL)",
            "removed_when_removed",
        ),
        check("memberships", "title IS NULL OR length(title) BETWEEN 1 AND 80", "title_length"),
        org_key("memberships"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
    )
    op.create_index("uq_memberships_org_user", "memberships", ["org_id", "user_id"], unique=True)
    # Политика RLS спрашивает активные членства человека в каждом операторе.
    op.create_index(
        "ix_memberships_active_user",
        "memberships",
        ["user_id"],
        postgresql_where=sa.text("state = 'active'"),
    )


def create_teams() -> None:
    """Teams and their members; a private team shows only to its members and admins."""
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False),
        org_column(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.Column("private", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("lead_membership_id", sa.Uuid(), nullable=True),
        moment("created_at", default_now=True),
        check("teams", "length(name) BETWEEN 1 AND 40", "name_length"),
        check("teams", "length(description) <= 140", "description_length"),
        check(
            "teams",
            "color IN ('blue', 'green', 'amber', 'violet', 'rose', 'sky')",
            "color_known",
        ),
        org_key("teams"),
        member_key("teams", "lead_membership_id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teams")),
    )
    op.create_index("ix_teams_org_id", "teams", ["org_id"])
    op.create_table(
        "team_members",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        org_column(),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name=op.f("fk_team_members_team_id_teams"),
            ondelete="CASCADE",
        ),
        member_key("team_members", "membership_id", "CASCADE"),
        org_key("team_members"),
        sa.PrimaryKeyConstraint("team_id", "membership_id", name=op.f("pk_team_members")),
    )
    op.create_index("ix_team_members_membership_id", "team_members", ["membership_id"])


def create_projects() -> None:
    """Projects: the shared context of a piece of work."""
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        org_column(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.Text(), server_default="planned", nullable=False),
        sa.Column("lead_membership_id", sa.Uuid(), nullable=True),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        moment("created_at", default_now=True),
        moment("updated_at", default_now=True),
        check("projects", "length(name) BETWEEN 1 AND 60", "name_length"),
        check("projects", "length(description) <= 400", "description_length"),
        check(
            "projects",
            "status IN ('planned', 'active', 'paused', 'completed')",
            "status_known",
        ),
        org_key("projects"),
        member_key("projects", "lead_membership_id", "SET NULL"),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name=op.f("fk_projects_team_id_teams"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index("ix_projects_org_id", "projects", ["org_id"])


def create_invitations() -> None:
    """Pending invitations: one-time links bound to an address, stored as SHA-256."""
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        org_column(),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "team_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column("token_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("invited_by_membership_id", sa.Uuid(), nullable=True),
        moment("sent_at", default_now=True),
        moment("expires_at"),
        sa.Column("accepted_membership_id", sa.Uuid(), nullable=True),
        moment("accepted_at", nullable=True),
        check("invitations", "length(email) BETWEEN 3 AND 254", "email_length"),
        check("invitations", "role IN ('admin', 'member')", "role_known"),
        check("invitations", "length(token_sha256) = 32", "token_digest_length"),
        check("invitations", "expires_at > sent_at", "expires_after_sent"),
        check(
            "invitations",
            "(accepted_at IS NULL) = (accepted_membership_id IS NULL)",
            "accepted_with_membership",
        ),
        org_key("invitations"),
        member_key("invitations", "invited_by_membership_id", "SET NULL"),
        member_key("invitations", "accepted_membership_id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
    )
    op.create_index("uq_invitations_token_sha256", "invitations", ["token_sha256"], unique=True)
    op.create_index(
        "uq_invitations_pending_email",
        "invitations",
        ["org_id", "email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL"),
    )


def create_access_tables() -> None:
    """Grants of `selected` rows and the records that share personal items into a workspace."""
    op.create_table(
        "resource_grants",
        org_column(),
        sa.Column("resource_kind", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("grantee_kind", sa.Text(), nullable=False),
        sa.Column("grantee_id", sa.Uuid(), nullable=False),
        moment("created_at", default_now=True),
        check("resource_grants", "resource_kind ~ '^[a-z][a-z0-9_]{0,31}$'", "resource_kind_form"),
        check("resource_grants", "grantee_kind IN ('member', 'team')", "grantee_kind_known"),
        org_key("resource_grants"),
        sa.PrimaryKeyConstraint(
            "org_id",
            "resource_kind",
            "resource_id",
            "grantee_kind",
            "grantee_id",
            name=op.f("pk_resource_grants"),
        ),
    )
    op.create_index(
        "ix_resource_grants_resource", "resource_grants", ["resource_kind", "resource_id"]
    )
    op.create_index("ix_resource_grants_grantee", "resource_grants", ["grantee_kind", "grantee_id"])
    op.create_table(
        "workspace_meeting_shares",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        org_column(),
        sa.Column("shared_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("access", sa.Text(), nullable=False),
        sa.Column("transcript_shared", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        moment("shared_at", default_now=True),
        moment("updated_at", default_now=True),
        check(
            "workspace_meeting_shares",
            "access IN ('selected', 'organization')",
            "access_known",
        ),
        org_key("workspace_meeting_shares"),
        member_key("workspace_meeting_shares", "shared_by_membership_id", "CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_workspace_meeting_shares_project_id_projects"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("session_id", name=op.f("pk_workspace_meeting_shares")),
    )
    op.create_index(
        "ix_workspace_meeting_shares_org", "workspace_meeting_shares", ["org_id", "shared_at"]
    )
    create_knowledge_items()


def create_knowledge_items() -> None:
    """Files and connected sources a workspace knows: uploads, members' files, sources."""
    op.create_table(
        "workspace_knowledge_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        org_column(),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column("connector_source_id", sa.Uuid(), nullable=True),
        sa.Column("access", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("added_by_membership_id", sa.Uuid(), nullable=True),
        moment("added_at", default_now=True),
        check(
            "workspace_knowledge_items",
            "source_kind IN ('upload', 'personal', 'connector')",
            "source_kind_known",
        ),
        check(
            "workspace_knowledge_items",
            "(source_kind = 'connector') = (connector_source_id IS NOT NULL) "
            "AND (source_kind = 'connector') = (file_id IS NULL)",
            "source_matches_kind",
        ),
        check(
            "workspace_knowledge_items",
            "access IN ('selected', 'organization')",
            "access_known",
        ),
        org_key("workspace_knowledge_items"),
        member_key("workspace_knowledge_items", "added_by_membership_id", "SET NULL"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_workspace_knowledge_items_project_id_projects"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_knowledge_items")),
    )
    op.create_index(
        "uq_workspace_knowledge_items_file",
        "workspace_knowledge_items",
        ["org_id", "file_id"],
        unique=True,
        postgresql_where=sa.text("file_id IS NOT NULL"),
    )


def create_audit() -> None:
    """The workspace audit log: ids and codes, monthly partitions kept 12 months."""
    op.create_table(
        "org_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        moment("created_at"),
        org_column(),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("actor_membership_id", sa.Uuid(), nullable=True),
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("value", sa.Text(), nullable=True),
        check("org_audit_events", f"action IN ({AUDIT_ACTIONS})", "action_known"),
        check("org_audit_events", f"target_kind ~ {CODE_FORM}", "target_kind_form"),
        check("org_audit_events", f"value IS NULL OR value ~ {CODE_FORM}", "value_form"),
        sa.PrimaryKeyConstraint("id", "created_at", name="pk_org_audit_events"),
        postgresql_partition_by=monthly_partition_range("created_at"),
    )
    op.create_index("ix_org_audit_events_org", "org_audit_events", ["org_id", "created_at"])
    register_monthly_partitions(AUDIT)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the audit log, the workspace tables, the owner rule and the membership function."""
    op.execute("DROP POLICY own_memberships ON memberships")
    # Политики ссылаются на app_member_org_ids(): снимаются раньше функции.
    for table in reversed(ISOLATED_TABLES):
        revoke_from_sweeper(table)
        revoke_from_application(scope, table)
        disable_company_isolation(table)
    unregister_monthly_partitions(AUDIT.table)
    op.drop_table("org_audit_events")
    op.execute("DROP TRIGGER memberships_keep_an_owner ON memberships")
    op.execute("DROP TRIGGER organizations_keep_an_owner ON organizations")
    op.execute("DROP FUNCTION workspaces_keep_an_owner()")
    for table in ("workspace_knowledge_items", "workspace_meeting_shares", "resource_grants"):
        op.drop_table(table)
    for table in ("invitations", "projects", "team_members", "teams"):
        op.drop_table(table)
    op.execute("DROP FUNCTION app_member_org_ids()")
    op.drop_table("memberships")
    op.drop_table("organizations")
