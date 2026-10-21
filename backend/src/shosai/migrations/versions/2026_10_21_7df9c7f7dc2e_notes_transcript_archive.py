"""The transcript archive: a meeting's pointer to its archived lines and the guarded drop (step 20).

A meeting of a month that ended more than 12 months ago keeps its transcript as gzipped
JSON lines in its home's bucket; `sessions.transcript_archive_key` points at the object and
`transcript_archive_lines` says how many lines it holds, both set only after the object was
read back and its lines counted again under the meeting's lock. A month's partition goes
only through `notes_drop_archived_partition`, owned by the migration role and run with its
rights by the sweep role: it drops `transcript_segments_pYYYYMM` only when no meeting of
that UTC month is left without its archive, and otherwise answers `unarchived`; the check
reads the partial index of unarchived meetings, never the partition's lines. A drop that
waits for its lock more than 2 s answers `deferred` and is tried on the next tick. The monthly
upkeep never drops these partitions (its policy keeps them, revision `a2c7e4f9b318`).
`meetings_live_facts` counts a meeting started more than 12 months ago as gone: the drain
stores no line of it, so the lines the archive took stay all of them. Every home.
"""

from typing import Final

import sqlalchemy as sa
from alembic import op

from shosai.core.db.database_roles import SWEEPER_ROLE
from shosai.core.db.migration_scope import (
    EVERY_HOME,
    FunctionArgument,
    MigrationScope,
    drop_function,
    open_function,
    runs_in,
)

revision: str = "7df9c7f7dc2e"
down_revision: str | None = "861ec10acf1d"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

DROP_ARCHIVED: Final = "notes_drop_archived_partition"
DROP_ARCHIVED_ARGUMENTS: Final[tuple[FunctionArgument, ...]] = ("text",)
POINTER_CHECK: Final = "ck_sessions_transcript_archive_pointer"
UNARCHIVED_INDEX: Final = "ix_sessions_unarchived"
# Месяц — «YYYYMM», по UTC, как и партиции. Строки партиции не читаются: при пяти миллионах
# строк в день их подсчёт не уложился бы в таймаут; каждую встречу сверил архиватор.
DROP_ARCHIVED_FUNCTION: Final = """
CREATE FUNCTION notes_drop_archived_partition(month text)
RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
SET lock_timeout = '2s'
AS $$
DECLARE
    child text;
    first_day timestamp;
BEGIN
    IF month !~ '^[0-9]{6}$' THEN
        RAISE EXCEPTION 'month must be YYYYMM';
    END IF;
    child := 'transcript_segments_p' || month;
    IF NOT EXISTS (
        SELECT 1 FROM pg_inherits AS i JOIN pg_class AS c ON c.oid = i.inhrelid
        WHERE i.inhparent = 'public.transcript_segments'::regclass AND c.relname = child
    ) THEN
        RETURN 'absent';
    END IF;
    first_day := to_date(month, 'YYYYMM')::timestamp;
    IF EXISTS (
        SELECT 1 FROM public.sessions
        WHERE transcript_archive_key IS NULL
            AND started_at >= first_day AT TIME ZONE 'UTC'
            AND started_at < (first_day + interval '1 month') AT TIME ZONE 'UTC'
    ) THEN
        RETURN 'unarchived';
    END IF;
    BEGIN
        EXECUTE format('DROP TABLE public.%I', child);
    EXCEPTION WHEN lock_not_available THEN
        RETURN 'deferred';
    END;
    RETURN 'dropped';
END
$$
"""
# Ушедшая встреча строк не принимает: удалённая или начатая больше 12 месяцев назад — её
# месяц уже может забирать архив (ARCHIVE_AFTER_MONTHS в domain/transcript_archive.py).
LIVE_FACTS: Final = """
CREATE OR REPLACE FUNCTION meetings_live_facts(uuid[])
RETURNS TABLE (
    id uuid, user_id uuid, org_id uuid, started_at timestamptz, kept boolean, status text,
    gone boolean
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT m.id, m.user_id, m.org_id, m.started_at, m.kept, m.status,
        m.deleted_at IS NOT NULL OR m.started_at < now() - interval '12 months'
    FROM sessions AS m WHERE m.id = ANY($1)
$$
"""
LIVE_FACTS_BEFORE: Final = """
CREATE OR REPLACE FUNCTION meetings_live_facts(uuid[])
RETURNS TABLE (
    id uuid, user_id uuid, org_id uuid, started_at timestamptz, kept boolean, status text,
    gone boolean
)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    SELECT m.id, m.user_id, m.org_id, m.started_at, m.kept, m.status, m.deleted_at IS NOT NULL
    FROM sessions AS m WHERE m.id = ANY($1)
$$
"""
ARCHIVED_EXIST: Final = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM sessions WHERE transcript_archive_key IS NOT NULL) THEN
        RAISE EXCEPTION 'transcripts are archived: bring them back before the downgrade';
    END IF;
END
$$
"""


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the pointer and the guarded drop of an archived month."""
    del scope
    op.add_column("sessions", sa.Column("transcript_archive_key", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("transcript_archive_lines", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f(POINTER_CHECK),
        "sessions",
        "(transcript_archive_key IS NULL AND transcript_archive_lines IS NULL) OR "
        "(transcript_archive_key LIKE 'archive/transcripts/%' AND transcript_archive_lines >= 0)",
    )
    # Архиватор и проверка перед удалением ищут встречи месяца без архива по началу.
    op.create_index(
        UNARCHIVED_INDEX,
        "sessions",
        ["started_at"],
        postgresql_where=sa.text("transcript_archive_key IS NULL"),
    )
    op.execute(DROP_ARCHIVED_FUNCTION)
    open_function(DROP_ARCHIVED, DROP_ARCHIVED_ARGUMENTS, (SWEEPER_ROLE,))
    # CREATE OR REPLACE сохраняет владельца и права функции.
    op.execute(LIVE_FACTS)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Refused while a transcript lives in the archive; otherwise drop the function and pointer."""
    del scope
    op.execute(ARCHIVED_EXIST)
    op.execute(LIVE_FACTS_BEFORE)
    drop_function(DROP_ARCHIVED, DROP_ARCHIVED_ARGUMENTS)
    op.drop_index(UNARCHIVED_INDEX, table_name="sessions")
    op.drop_constraint(op.f(POINTER_CHECK), "sessions", type_="check")
    op.drop_column("sessions", "transcript_archive_lines")
    op.drop_column("sessions", "transcript_archive_key")
