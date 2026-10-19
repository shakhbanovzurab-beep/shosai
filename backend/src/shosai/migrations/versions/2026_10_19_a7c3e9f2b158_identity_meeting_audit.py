"""Support's actions on a person's meetings in the admin's audit log, EU home only (step 8).

The admin listing a person's deleted meetings and restoring one are recorded like the
files' actions (`d8b3e6a0f914`); a row names the meeting it touched by its id.
"""

from alembic import op

from shosai.core.db.migration_scope import MigrationScope, runs_in
from shosai.core.kernel.homes import Home

revision: str = "a7c3e9f2b158"
down_revision: str | None = "f2b6d1c9a473"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

CONSTRAINT = "ck_operator_audit_events_action_known"
BEFORE = (
    "'operator_roles_changed', 'account_blocked', 'account_unblocked', 'account_banned', "
    "'account_transfer_requested', 'account_transfer_cancelled', 'files_listed', 'file_restored'"
)
AFTER = BEFORE + ", 'meetings_listed', 'meeting_restored'"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit the two meeting actions."""
    del scope
    op.drop_constraint(op.f(CONSTRAINT), "operator_audit_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "operator_audit_events", f"action IN ({AFTER})")


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Admit the earlier actions only; meeting rows must be gone first."""
    del scope
    op.execute(
        "DELETE FROM operator_audit_events WHERE action IN ('meetings_listed', 'meeting_restored')"
    )
    op.drop_constraint(op.f(CONSTRAINT), "operator_audit_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "operator_audit_events", f"action IN ({BEFORE})")
