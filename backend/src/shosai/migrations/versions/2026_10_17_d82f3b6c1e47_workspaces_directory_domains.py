"""Company email domains across both homes, in the EU home only (workspaces step 2).

A verified domain belongs to one workspace, whatever its home: the first verification
wins (ADR 0053 point 3). The table holds a domain, ids, a home and a token — no personal
data (§6) — and is read by domain before anyone belongs to the workspace, so it has no
row-level security; only workspaces reaches it.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    APPLICATION_WRITES,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)
from shosai.core.kernel.homes import Home

revision: str = "d82f3b6c1e47"
down_revision: str | None = "c41d7e9a2b85"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the domain directory, open to the application role."""
    op.create_table(
        "directory_domains",
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("home", sa.Text(), nullable=False),
        sa.Column("txt_token", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "domain ~ '^[a-z0-9.-]{3,253}$'", name=op.f("ck_directory_domains_domain_form")
        ),
        sa.CheckConstraint("home IN ('ru', 'eu')", name=op.f("ck_directory_domains_home_known")),
        sa.CheckConstraint(
            "txt_token ~ '^[A-Za-z0-9_-]{32,64}$'", name=op.f("ck_directory_domains_txt_token_form")
        ),
        sa.PrimaryKeyConstraint("domain", name=op.f("pk_directory_domains")),
    )
    # Один домен у пространства: кабинет показывает одно поле join_domain.
    op.create_index("uq_directory_domains_org_id", "directory_domains", ["org_id"], unique=True)
    grant_to_application(scope, "directory_domains", APPLICATION_WRITES)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the domain directory."""
    revoke_from_application(scope, "directory_domains")
    op.drop_table("directory_domains")
