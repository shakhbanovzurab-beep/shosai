"""A ban the admin wrote names the admin as its author (meetings A8, MR-D10).

The admin's LiveKit screen removes a participant like the owner does, with a ban; the admin
is not a principal of the call, so `banned_by` admits `admin` beside a principal.
"""

from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "60cb2ba1c6aa"
down_revision: str | None = "b77d3c18b606"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLE = "room_bans"
CONSTRAINT = "ck_room_bans_banned_by_shape"
PRINCIPAL = (
    "banned_by ~ "
    "'^(guest-[0-9a-f]{12}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$'"
)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit the admin as a ban's author."""
    del scope
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, f"banned_by = 'admin' OR {PRINCIPAL}")


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Admit principals only; the admin's bans are taken over by the room's owner first."""
    del scope
    op.execute("UPDATE room_bans SET banned_by = owner_id::text WHERE banned_by = 'admin'")
    op.drop_constraint(op.f(CONSTRAINT), TABLE, type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), TABLE, PRINCIPAL)
