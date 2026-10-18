"""Support's actions on a person's files in the admin's audit log, EU home only (files step 7).

The admin listing a person's deleted files and restoring one are recorded like the account
actions; a row names the file it touched by its id.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import MigrationScope, runs_in
from shosai.core.kernel.homes import Home

revision: str = "d8b3e6a0f914"
down_revision: str | None = "c4f9a1e7d250"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

CONSTRAINT = "ck_operator_audit_events_action_known"
BEFORE = (
    "'operator_roles_changed', 'account_blocked', 'account_unblocked', 'account_banned', "
    "'account_transfer_requested', 'account_transfer_cancelled'"
)
AFTER = BEFORE + ", 'files_listed', 'file_restored'"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit the two file actions and the id of what an action touched."""
    del scope
    op.add_column("operator_audit_events", sa.Column("subject_id", sa.Uuid(), nullable=True))
    op.drop_constraint(op.f(CONSTRAINT), "operator_audit_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "operator_audit_events", f"action IN ({AFTER})")


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Admit the earlier actions only; file rows must be gone first."""
    del scope
    op.execute(
        "DELETE FROM operator_audit_events WHERE action IN ('files_listed', 'file_restored')"
    )
    op.drop_constraint(op.f(CONSTRAINT), "operator_audit_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "operator_audit_events", f"action IN ({BEFORE})")
    op.drop_column("operator_audit_events", "subject_id")
