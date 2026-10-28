"""Connectors' grant lifecycle (connectors step 4; ADR 0075).

A grant marked `revoking` waits for its provider's revocation: `revoke_at` is when it falls
due, moved forward by the claim of the task that revokes it; a revoking grant always has it.
The due rows of the revocation and of the keep-alive refresh are found by partial indexes
on (due column, key), as the scheduler's sweeps read them.
"""

from typing import Final

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "4b32f8e17344"
down_revision: str | None = "81bcb965a31c"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

GRANTS: Final = "connector_grants"
SECRETS: Final = "connector_grant_secrets"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the revocation's due column and the due indexes."""
    del scope
    op.add_column(GRANTS, sa.Column("revoke_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE connector_grants SET revoke_at = now() "
        "WHERE status = 'revoking' AND revoke_at IS NULL"
    )
    op.create_check_constraint(
        op.f("ck_connector_grants_revoke_due"), GRANTS,
        "(status = 'revoking') = (revoke_at IS NOT NULL)",
    )  # fmt: skip
    op.create_index(
        "ix_connector_grants_revoke_due", GRANTS, ["revoke_at", "id"],
        postgresql_where=sa.text("status = 'revoking'"),
    )  # fmt: skip
    op.drop_index("ix_connector_grant_secrets_keepalive_at", table_name=SECRETS)
    op.create_index(
        "ix_connector_grant_secrets_keepalive_due", SECRETS, ["keepalive_at", "grant_id"],
        postgresql_where=sa.text("keepalive_at IS NOT NULL"),
    )  # fmt: skip


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop what this revision added, the keep-alive's first index back."""
    del scope
    op.drop_index("ix_connector_grant_secrets_keepalive_due", table_name=SECRETS)
    op.create_index(
        "ix_connector_grant_secrets_keepalive_at", SECRETS, ["keepalive_at"],
        postgresql_where=sa.text("keepalive_at IS NOT NULL"),
    )  # fmt: skip
    op.drop_index("ix_connector_grants_revoke_due", table_name=GRANTS)
    op.drop_constraint(op.f("ck_connector_grants_revoke_due"), GRANTS, type_="check")
    op.drop_column(GRANTS, "revoke_at")
