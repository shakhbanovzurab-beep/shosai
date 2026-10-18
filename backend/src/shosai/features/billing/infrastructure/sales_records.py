"""A person's sales inquiries in their home (revision `d4a8b1f3e602`)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

TEAM_SIZES = "'1-10', '11-50', '51-200', '201-1000', '1000+'"


class SalesInquiryRecord(ModelBase):
    """A request about a custom-priced plan."""

    __tablename__ = "sales_inquiries"
    __table_args__ = (
        CheckConstraint("length(work_email) BETWEEN 3 AND 254", name="email_length"),
        CheckConstraint("length(company) BETWEEN 1 AND 120", name="company_length"),
        CheckConstraint(f"team_size IN ({TEAM_SIZES})", name="team_size_known"),
        CheckConstraint("length(message) <= 2000", name="message_length"),
        Index("ix_sales_inquiries_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    work_email: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(Text)
    team_size: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
