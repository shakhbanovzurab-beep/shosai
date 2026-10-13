"""How a table is partitioned by month, and the helpers its migration uses (§8.2; F1 audit A8).

A high-volume table is a range-partitioned parent on a `timestamptz` column, one partition
per calendar month in UTC, named `<table>_pYYYYMM`. Its migration creates the parent with
`postgresql_partition_by=monthly_partition_range(column)` — the column is part of the
primary key, as PostgreSQL requires — and registers its policy with
`register_monthly_partitions`: how many months ahead must exist and how many past months
are kept (none: kept for ever, as usage tombstones are, ADR 0007). Registering creates
the partitions due now, so the table takes rows at once; the upkeep tick keeps the window
moving.

The policy lives in `partition_policies`, which only migrations write. Partitions are
created and dropped by `maintain_monthly_partitions(table)`, a function owned by the
migration role and run with its rights: the application role may call it, but it acts only
on a registered table and only by its policy. Partitions get no grants, so the application
reaches rows only through the parent and the parent's row-level security always applies.
No default partition exists — a row outside
every partition fails loudly — so a stalled upkeep pages before the window ends.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import sqlalchemy as sa
from alembic import op

POLICY_TABLE: Final = "partition_policies"
MAINTAIN_FUNCTION: Final = "maintain_monthly_partitions"
TABLE_NAME: Final = re.compile(r"[a-z][a-z0-9_]{0,54}")
# Имя партиции: таблица и месяц UTC. Тест схемы и автогенерация не считают их таблицами модели.
PARTITION_NAME: Final = re.compile(r"[a-z][a-z0-9_]*_p[0-9]{6}")
LONGEST_AHEAD: Final = 12

policies = sa.table(
    POLICY_TABLE,
    sa.column("table_name", sa.Text()),
    sa.column("ahead_months", sa.Integer()),
    sa.column("keep_months", sa.Integer()),
)


def maintain(table: str) -> sa.Select[tuple[str, ...]]:
    """`SELECT * FROM maintain_monthly_partitions(:table)`: create due, drop expired."""
    call = getattr(sa.func, MAINTAIN_FUNCTION)(table)
    return sa.select(sa.text("*")).select_from(call)


@dataclass(frozen=True, slots=True)
class MonthlyPartitions:
    """A table's partition policy: months kept ahead and past months kept (None: all)."""

    table: str
    ahead_months: int = 2
    keep_months: int | None = None

    def __post_init__(self) -> None:
        if not TABLE_NAME.fullmatch(self.table):
            message = "таблица с партициями — имя в snake_case до 55 символов"
            raise ValueError(message)
        if not 1 <= self.ahead_months <= LONGEST_AHEAD:
            message = f"партиции вперёд — от 1 до {LONGEST_AHEAD} месяцев"
            raise ValueError(message)
        if self.keep_months is not None and self.keep_months < 1:
            message = "хранятся хотя бы прошлый месяц или все месяцы"
            raise ValueError(message)


def monthly_partition_range(column: str) -> str:
    """The `postgresql_partition_by` of a parent partitioned by month (migration and model)."""
    if not TABLE_NAME.fullmatch(column):
        message = "столбец партиционирования — имя в snake_case"
        raise ValueError(message)
    return f"RANGE ({column})"


def register_monthly_partitions(policy: MonthlyPartitions) -> None:
    """Record the policy of a new parent and create its partitions due now (migration step)."""
    op.execute(
        sa.insert(policies).values(
            table_name=policy.table,
            ahead_months=policy.ahead_months,
            keep_months=policy.keep_months,
        )
    )
    op.execute(maintain(policy.table))


def unregister_monthly_partitions(table: str) -> None:
    """Forget a parent's policy before its downgrade drops it with its partitions."""
    op.execute(sa.delete(policies).where(policies.c.table_name == table))


def is_model_table(name: str | None, type_: str, _parent_names: Sequence[object] | object) -> bool:
    """Alembic's `include_name`: a monthly partition is not a table of the models."""
    return not (type_ == "table" and name is not None and PARTITION_NAME.fullmatch(name))
