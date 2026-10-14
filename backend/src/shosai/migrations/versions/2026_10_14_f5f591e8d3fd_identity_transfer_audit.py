"""Transfers in the operators' audit log, EU home only (identity step 9)."""

from alembic import op

from shosai.core.db.migration_scope import MigrationScope, runs_in
from shosai.core.kernel.homes import Home

revision: str = "f5f591e8d3fd"
down_revision: str | None = "a2d9b4709a2e"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

CONSTRAINT = "ck_operator_audit_events_action_known"
BEFORE = "'operator_roles_changed', 'account_blocked', 'account_unblocked', 'account_banned'"
AFTER = BEFORE + ", 'account_transfer_requested', 'account_transfer_cancelled'"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit the two transfer actions."""
    op.drop_constraint(op.f(CONSTRAINT), "operator_audit_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "operator_audit_events", f"action IN ({AFTER})")


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Admit the earlier actions only; transfer rows must be gone first."""
    op.execute(
        "DELETE FROM operator_audit_events "
        "WHERE action IN ('account_transfer_requested', 'account_transfer_cancelled')"
    )
    op.drop_constraint(op.f(CONSTRAINT), "operator_audit_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "operator_audit_events", f"action IN ({BEFORE})")
