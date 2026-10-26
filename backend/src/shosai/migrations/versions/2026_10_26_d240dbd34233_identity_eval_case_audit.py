"""The owner's reads of Leo's evaluation cases in the admin's audit log, EU home only (agent step
11c; ADR 0068 AG-D13).

A case is a person's conversation they let help improve the models; every read of one on the
host — shown to the owner or replayed by the live suite — is recorded like the support actions,
a row naming the case by its id and never its content.
"""

from alembic import op

from shosai.core.db.migration_scope import MigrationScope, runs_in
from shosai.core.kernel.homes import Home

revision: str = "d240dbd34233"
down_revision: str | None = "3f85ef4b625e"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

TABLE = "operator_audit_events"
CONSTRAINT = "ck_operator_audit_events_action_known"
BEFORE = (
    "'operator_roles_changed', 'account_blocked', 'account_unblocked', 'account_banned', "
    "'account_transfer_requested', 'account_transfer_cancelled', 'files_listed', 'file_restored', "
    "'meetings_listed', 'meeting_restored'"
)
AFTER = BEFORE + ", 'eval_case_read'"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit the read of an evaluation case."""
    del scope
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, f"action IN ({AFTER})")


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Admit the earlier actions only; the case reads' rows must be gone first."""
    del scope
    op.execute("DELETE FROM operator_audit_events WHERE action = 'eval_case_read'")
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, f"action IN ({BEFORE})")
