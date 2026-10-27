"""The admin's closes of call rooms and removals from them in the audit log, EU home only
(meetings A8, ADR 0072 MR-D10).

The admin's LiveKit screen ends a room for everyone or removes one participant; each is recorded
like the support actions, a row naming the room by its id, the room's owner as the target.
"""

from alembic import op

from shosai.core.db.migration_scope import MigrationScope, runs_in
from shosai.core.kernel.homes import Home

revision: str = "b77d3c18b606"
down_revision: str | None = "8361e51e899c"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

TABLE = "operator_audit_events"
CONSTRAINT = "ck_operator_audit_events_action_known"
BEFORE = (
    "'operator_roles_changed', 'account_blocked', 'account_unblocked', 'account_banned', "
    "'account_transfer_requested', 'account_transfer_cancelled', 'files_listed', 'file_restored', "
    "'meetings_listed', 'meeting_restored', 'eval_case_read'"
)
AFTER = BEFORE + ", 'room_closed', 'room_participant_removed'"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit the room actions."""
    del scope
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, f"action IN ({AFTER})")


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Admit the earlier actions only; the room actions' rows must be gone first."""
    del scope
    op.execute(
        "DELETE FROM operator_audit_events "
        "WHERE action IN ('room_closed', 'room_participant_removed')"
    )
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, f"action IN ({BEFORE})")
