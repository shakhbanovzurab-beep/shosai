"""A room's video recording names its File Manager file (meetings A7, MR-D4).

The recording becomes the owner's File Manager file under the recording's own id, written by
egress straight at that file's key, so the row names the file it became rather than a held
object: `held_object_id` is renamed `file_id`. No row has a value yet.
"""

from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "8361e51e899c"
down_revision: str | None = "519b43bd170b"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Rename the column."""
    op.alter_column("room_recordings", "held_object_id", new_column_name="file_id")


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Rename it back."""
    op.alter_column("room_recordings", "file_id", new_column_name="held_object_id")
