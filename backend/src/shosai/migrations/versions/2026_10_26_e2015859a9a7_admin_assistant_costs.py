"""Cost rows of the admin panel's Leo: the platform account `admin_assistant` (every home).

Agent step 16a (ADR 0068 AG-D5) made the platform pay the operator's turns from a new account,
but the check on `provider_costs` still named only the three before it, so the first operator
turn failed when its cost was written.
"""

from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "e2015859a9a7"
down_revision: str | None = "5979d6f23013"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

NAME = "ck_provider_costs_platform_account_known"
ACCOUNTS = "platform_account IN ('landing_demo', 'help_assistant', 'admin_assistant', 'system')"
FORMER_ACCOUNTS = "platform_account IN ('landing_demo', 'help_assistant', 'system')"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit the admin panel's Leo as a platform account of cost rows."""
    op.drop_constraint(op.f(NAME), "provider_costs", type_="check")
    op.create_check_constraint(op.f(NAME), "provider_costs", ACCOUNTS)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Return to the former accounts; refused while such rows exist, which are kept 5 years."""
    op.drop_constraint(op.f(NAME), "provider_costs", type_="check")
    op.create_check_constraint(op.f(NAME), "provider_costs", FORMER_ACCOUNTS)
