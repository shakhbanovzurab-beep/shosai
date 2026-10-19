"""The admin's audit log in the EU (§3.5, SM-12, ADR 0049).

The log holds ids and codes only, keeps 12 months in monthly partitions and is append-only
for the application: its role may insert and read, never update or delete (nfr-17).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    PrimaryKeyConstraint,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase, table_info
from shosai.core.db.partitions.policy import monthly_partition_range
from shosai.core.kernel.homes import Home

# Роли операторов и бан ушли (ADR 0049), но их строки за прошлые месяцы остаются в журнале.
ACTIONS = (
    "'operator_roles_changed', 'account_blocked', 'account_unblocked', 'account_banned', "
    "'account_transfer_requested', 'account_transfer_cancelled', 'files_listed', 'file_restored', "
    "'meetings_listed', 'meeting_restored'"
)


class OperatorAuditEvent(ModelBase):
    """One admin action: on whom in which home, what and why, as codes."""

    __tablename__ = "operator_audit_events"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_operator_audit_events"),
        CheckConstraint(f"action IN ({ACTIONS})", name="action_known"),
        CheckConstraint("target_home IN ('ru', 'eu')", name="target_home_known"),
        CheckConstraint(
            "reason_code IS NULL OR reason_code ~ '^[a-z0-9_.:-]{1,64}$'", name="reason_code_form"
        ),
        Index("ix_operator_audit_events_target", "target_user_id", "created_at"),
        Index("ix_operator_audit_events_operator", "operator_id", "created_at"),
        {
            "postgresql_partition_by": monthly_partition_range("created_at"),
            "info": table_info(homes=(Home.EU,)),
        },
    )

    # Идентификатор события outbox: повторная доставка не пишет вторую строку.
    id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    operator_id: Mapped[UUID | None] = mapped_column(Uuid)
    target_user_id: Mapped[UUID] = mapped_column(Uuid)
    target_home: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    reason_code: Mapped[str | None] = mapped_column(Text)
    subject_id: Mapped[UUID | None] = mapped_column(Uuid)


OPERATOR_MODELS = (OperatorAuditEvent,)
