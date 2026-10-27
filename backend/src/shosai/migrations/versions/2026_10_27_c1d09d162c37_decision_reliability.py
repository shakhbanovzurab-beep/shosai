"""Reliability per band in the EU home (decisions step 8b; ADR 0069 DL-D7).

`decision_reliability` keeps, per day and home, the counts of the daily pass: decisions per
point, version, revision, shadow flag, band, language and source, and how many of them the
careful outcome's case followed. Numbers and codes only, no id and no text: platform data
without an owner. The application reads it, and replaces a day of a home by deleting and
inserting it in one transaction, so a pass run twice leaves the same rows.
"""

from typing import Any

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)
from shosai.core.kernel.homes import Home

revision: str = "c1d09d162c37"
down_revision: str | None = "a1a96ace53e1"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

TABLE = "decision_reliability"
KEY = ("day", "home", "point", "version", "revision", "shadow", "band", "language", "source")
CHECKS = (
    ("home_known", "home IN ('ru', 'eu')"),
    ("point_form", "point ~ '^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$'"),
    ("versions", "version >= 1 AND revision >= 0"),
    ("band_form", "band ~ '^[a-z0-9_.,:-]+$' AND length(band) <= 64"),
    ("language_form", "language ~ '^[a-z]{2,3}(-[A-Za-z]{2,4})?$'"),
    ("source_known", "source IN ('rule', 'fallback', 'jev', 'late')"),
    ("counts", "decisions >= 1 AND positives BETWEEN 0 AND decisions"),
)


def columns() -> tuple[sa.Column[Any], ...]:
    """The key and the two counts."""
    return (
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("home", sa.Text(), nullable=False),
        sa.Column("point", sa.Text(), nullable=False),
        sa.Column("version", sa.SmallInteger(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("shadow", sa.Boolean(), nullable=False),
        sa.Column("band", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("decisions", sa.Integer(), nullable=False),
        sa.Column("positives", sa.Integer(), nullable=False),
    )


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Create the counts in the EU home."""
    if scope.home is not Home.EU:
        return
    op.create_table(
        TABLE,
        *columns(),
        *(sa.CheckConstraint(sql, name=op.f(f"ck_{TABLE}_{name}")) for name, sql in CHECKS),
        sa.PrimaryKeyConstraint(*KEY, name=op.f(f"pk_{TABLE}")),
    )
    grant_to_application(scope, TABLE, ("SELECT", "INSERT", "DELETE"))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop them."""
    if scope.home is not Home.EU:
        return
    revoke_from_application(scope, TABLE)
    op.drop_table(TABLE)
