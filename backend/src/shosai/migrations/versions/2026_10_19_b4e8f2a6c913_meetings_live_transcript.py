"""Meetings' live transcript and sweeps, in each home (meetings step 4).

`sessions.settled_at` marks an ended meeting whose transcript was checked against what
capture showed (inv-6) and which got its run if it was spoken (inv-7); a line drained after
that clears the mark, so the meeting is settled again. `sessions.lines_missing` keeps the
lines already reported lost, so a second settling reports only new losses.
`meetings_live_facts(ids)` answers, past row-level security, what the transcript's drain
needs of each meeting — its owner,
company, start, whether it is kept and whether it is gone — and nothing else, so lines of
any company are stored in their company's scope. The sweep role reads meetings and their
lines to list what is due; each meeting is then ended or settled in its owner's scope.
"""

from typing import Final

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    FunctionArgument,
    MigrationScope,
    drop_function,
    grant_to_sweeper,
    open_function,
    revoke_from_sweeper,
    runs_in,
)

revision: str = "b4e8f2a6c913"
down_revision: str | None = "a2c7e4f9b318"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

LIVE_FACTS: Final = "meetings_live_facts"
LIVE_FACTS_ARGUMENTS: Final[tuple[FunctionArgument, ...]] = ("uuid[]",)
# Владелец таблиц отвечает фактами о встречах для слива строк; ни названий, ни текста не отдаёт.
LIVE_FACTS_FUNCTION: Final = """
CREATE FUNCTION meetings_live_facts(uuid[])
RETURNS TABLE (
    id uuid, user_id uuid, org_id uuid, started_at timestamptz, kept boolean, status text,
    gone boolean
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT m.id, m.user_id, m.org_id, m.started_at, m.kept, m.status, m.deleted_at IS NOT NULL
    FROM sessions AS m WHERE m.id = ANY($1)
$$
"""
SWEPT: Final = ("sessions", "transcript_segments")


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the settled mark, the drain's facts and the sweeps' reads."""
    op.add_column("sessions", sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("lines_missing", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "ix_sessions_unsettled",
        "sessions",
        ["ended_at"],
        postgresql_where=sa.text("status <> 'active' AND settled_at IS NULL"),
    )
    op.execute(LIVE_FACTS_FUNCTION)
    open_function(LIVE_FACTS, LIVE_FACTS_ARGUMENTS, (scope.application_role,))
    for table in SWEPT:
        grant_to_sweeper(table, ("SELECT",))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the sweeps' reads, the drain's facts and the settled mark."""
    del scope
    for table in reversed(SWEPT):
        revoke_from_sweeper(table)
    drop_function(LIVE_FACTS, LIVE_FACTS_ARGUMENTS)
    op.drop_index("ix_sessions_unsettled", table_name="sessions")
    op.drop_column("sessions", "lines_missing")
    op.drop_column("sessions", "settled_at")
