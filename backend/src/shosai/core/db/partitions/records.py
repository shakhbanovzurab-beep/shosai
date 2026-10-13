"""The partition policy of each partitioned table, in every home (§8.2; F1 audit A8).

Migrations write it when they create a partitioned parent and remove it before they drop
one; the application only reads which tables the upkeep tick serves.
"""

from sqlalchemy import CheckConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase


class PartitionPolicy(ModelBase):
    """How many months ahead a table's partitions exist and how many past months stay."""

    __tablename__ = "partition_policies"
    __table_args__ = (
        CheckConstraint("table_name ~ '^[a-z][a-z0-9_]{0,54}$'", name="table_name_format"),
        CheckConstraint("ahead_months BETWEEN 1 AND 12", name="ahead_bounded"),
        CheckConstraint("keep_months >= 1", name="keep_positive"),
    )

    table_name: Mapped[str] = mapped_column(Text, primary_key=True)
    ahead_months: Mapped[int] = mapped_column(Integer)
    # NULL — месяцы не удаляются: так живут надгробия расхода (ADR 0007).
    keep_months: Mapped[int | None] = mapped_column(Integer)
