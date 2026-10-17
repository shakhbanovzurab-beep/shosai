"""The workspace audit log and the company domain directory (workspaces plan §3.4).

The audit log holds ids and codes, keeps 12 months in monthly partitions and is append-only
for the application (inv-17). The domain directory lives in the EU home only and maps a
verified company domain to its workspace across both homes (ADR 0053 point 3).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, PrimaryKeyConstraint, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase, table_info
from shosai.core.db.partitions.policy import monthly_partition_range
from shosai.core.kernel.homes import Home
from shosai.features.workspaces.domain.audit import AuditAction

ACTIONS = ", ".join(f"'{action.value}'" for action in AuditAction)
CODE_FORM = "'^[a-z0-9_.:-]{1,64}$'"


class OrgAuditEvent(ModelBase):
    """One administrative action or access change inside a workspace."""

    __tablename__ = "org_audit_events"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_org_audit_events"),
        CheckConstraint(f"action IN ({ACTIONS})", name="action_known"),
        CheckConstraint(f"target_kind ~ {CODE_FORM}", name="target_kind_form"),
        CheckConstraint(f"value IS NULL OR value ~ {CODE_FORM}", name="value_form"),
        Index("ix_org_audit_events_org", "org_id", "created_at"),
        {"postgresql_partition_by": monthly_partition_range("created_at")},
    )

    id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Без внешнего ключа: журнал секционирован; стирает его сага удаления пространства.
    org_id: Mapped[UUID] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(Text)
    # Пусто — администратор платформы.
    actor_membership_id: Mapped[UUID | None] = mapped_column(Uuid)
    target_kind: Mapped[str] = mapped_column(Text)
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    value: Mapped[str | None] = mapped_column(Text)


class DirectoryDomain(ModelBase):
    """A company domain, its workspace and home, and the TXT token that proves it."""

    __tablename__ = "directory_domains"
    __table_args__ = (
        CheckConstraint("domain ~ '^[a-z0-9.-]{3,253}$'", name="domain_form"),
        CheckConstraint("home IN ('ru', 'eu')", name="home_known"),
        CheckConstraint("txt_token ~ '^[A-Za-z0-9_-]{32,64}$'", name="txt_token_form"),
        Index("uq_directory_domains_org_id", "org_id", unique=True),
        {"info": table_info(homes=(Home.EU,))},
    )

    domain: Mapped[str] = mapped_column(Text, primary_key=True)
    org_id: Mapped[UUID] = mapped_column(Uuid)
    home: Mapped[str] = mapped_column(Text)
    txt_token: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
