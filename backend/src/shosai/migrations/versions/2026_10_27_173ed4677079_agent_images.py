"""The operator's pictures in each home (agent step 16b2, AG-D5, AG-D10).

`agent_images` points at a picture's object in the bucket (`platform/agent/images/{id}`, ADR
0055) by the run that drew it. A deleted row leaves its key in `agent_image_releases` through a
trigger in the same transaction, so every way a thread goes takes its pictures' objects with
it; the release tick deletes them as the sweep role. Both tables are personal by row-level
security.
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    disable_user_isolation,
    enable_user_isolation,
    grant_to_application,
    grant_to_sweeper,
    revoke_from_application,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "173ed4677079"
down_revision: str | None = "fb74f9126b03"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLES = ("agent_images", "agent_image_releases")
RELEASED_FUNCTION = """
CREATE FUNCTION agent_image_released() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
BEGIN
    INSERT INTO agent_image_releases (object_key, user_id)
    VALUES (OLD.object_key, OLD.user_id)
    ON CONFLICT (object_key) DO NOTHING;
    RETURN NULL;
END
$$
"""
RELEASED_TRIGGER = """
CREATE TRIGGER agent_images_released AFTER DELETE ON agent_images
FOR EACH ROW EXECUTE FUNCTION agent_image_released()
"""


def check(table: str, sql: str, name: str) -> sa.CheckConstraint:
    """A check constraint named by the project's convention."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def moment(name: str) -> sa.Column[datetime]:
    """A moment, now by default."""
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the pictures, their releases and the trigger between them."""
    op.create_table(
        "agent_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        moment("created_at"),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        check(
            "agent_images",
            "content_type IN ('image/jpeg', 'image/png', 'image/webp')",
            "type_known",
        ),
        check("agent_images", "size_bytes BETWEEN 1 AND 10485760", "size_range"),
        check("agent_images", "width > 0 AND height > 0", "dimensions_positive"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_images")),
        sa.UniqueConstraint("object_key", name=op.f("uq_agent_images_object_key")),
    )
    op.create_index("ix_agent_images_run", "agent_images", ["user_id", "run_id"])
    op.create_table(
        "agent_image_releases",
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        moment("created_at"),
        sa.PrimaryKeyConstraint("object_key", name=op.f("pk_agent_image_releases")),
    )
    for table in TABLES:
        enable_user_isolation(table)
        grant_to_application(scope, table)
    grant_to_sweeper("agent_image_releases", ("SELECT", "DELETE"))
    op.execute(RELEASED_FUNCTION)
    op.execute(RELEASED_TRIGGER)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the trigger, the releases and the pictures."""
    op.execute("DROP TRIGGER agent_images_released ON agent_images")
    op.execute("DROP FUNCTION agent_image_released()")
    revoke_from_sweeper("agent_image_releases")
    for table in reversed(TABLES):
        revoke_from_application(scope, table)
        disable_user_isolation(table)
        op.drop_table(table)
