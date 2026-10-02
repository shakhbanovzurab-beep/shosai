"""${message}"""

import sqlalchemy as sa
from alembic import op

from whisperer.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | None = ${repr(branch_labels)}
depends_on: str | None = ${repr(depends_on)}
# Дома, где ревизия меняет схему (ADR 0010). Ревизия либо для всех домов, либо для одного
# набора; ревизия для обоих и для одного дома сразу делится на две.
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """${message}."""
    ${upgrades if upgrades else "raise NotImplementedError"}


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Undo: ${message}."""
    ${downgrades if downgrades else "raise NotImplementedError"}
