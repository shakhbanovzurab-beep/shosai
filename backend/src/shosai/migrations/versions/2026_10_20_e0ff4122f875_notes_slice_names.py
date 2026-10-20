"""The names the slice wrote into data follow its rename `meetings` → `notes` (ADR 0057).

Event types in the outbox, the consumers' delivery marks, the periodic jobs' last runs, the
effect scopes and identity's erased and copied owners keep the slice's old name in rows
written before; renamed with the code, nothing is delivered, run or erased twice. The cost
rows are append-only money history and keep the names they were written with. Every home.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "e0ff4122f875"
down_revision: str | None = "d7fdb62f4fd0"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

EVENT_TYPES = (
    ("meetings.meeting.ended", "notes.meeting.ended"),
    ("meetings.notes.ready", "notes.meeting.notes_ready"),
    ("meetings.meeting.deleted", "notes.meeting.deleted"),
    ("meetings.meeting.restored", "notes.meeting.restored"),
)
CONSUMERS = (
    ("meetings.hide_with_account", "notes.hide_with_account"),
    ("meetings.show_with_account", "notes.show_with_account"),
)
JOBS = (
    ("meetings.end_forgotten", "notes.end_forgotten"),
    ("meetings.settle_ended", "notes.settle_ended"),
    ("meetings.recover_runs", "notes.recover_runs"),
    ("meetings.purge_hidden", "notes.purge_hidden"),
)
SCOPES = (
    ("meetings.folder_create", "notes.folder_create"),
    ("meetings.template_create", "notes.template_create"),
    ("meetings.write_up_rewrite", "notes.write_up_rewrite"),
)
OWNERS = (("account_deletions", "erased_owners"), ("home_transfers", "copied_owners"))


def _rename(old: int, new: int) -> None:
    """Move every stored name from the `old` side of the pairs to the `new` one."""
    for table, column, pairs in (
        ("outbox_messages", "event_type", EVENT_TYPES),
        ("processed_events", "consumer", CONSUMERS),
        ("schedule_runs", "job_name", JOBS),
        ("effect_keys", "scope", SCOPES),
    ):
        rows = sa.table(table, sa.column(column, sa.Text()))
        for pair in pairs:
            op.execute(rows.update().where(rows.c[column] == pair[old]).values({column: pair[new]}))
    names = ("meetings", "notes")
    for table, column in OWNERS:
        rows = sa.table(table, sa.column(column, ARRAY(sa.Text())))
        op.execute(
            rows.update()
            .where(sa.literal(names[old]) == sa.func.any(rows.c[column]))
            .values({column: sa.func.array_replace(rows.c[column], names[old], names[new])})
        )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Rename the stored names to the slice's new one."""
    del scope
    _rename(0, 1)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Rename them back."""
    del scope
    _rename(1, 0)
