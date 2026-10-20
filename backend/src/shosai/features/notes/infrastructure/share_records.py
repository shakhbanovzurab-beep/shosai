"""A meeting's share link and its comments, in each home (revision `a2c7e4f9b318`; MT-D5).

A meeting has at most one link; its token is unique in the home and kept verbatim for
links migrated from the draft. Turning the link off deletes the row and, with it, the
comments. Who opens a link has no account: `meetings_shared_meeting(token)` answers, past
row-level security, only the meeting and the company of the link with that token, and the
page is then read in that company's scope, with the token checked in the same query.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.notes.infrastructure.meeting_records import meeting_reference

SHARED_MEETING_FUNCTION: Final = "meetings_shared_meeting"


class ShareLinkRecord(ModelBase):
    """A meeting's one share link and its settings."""

    __tablename__ = "meeting_result_shares"
    __table_args__ = (
        CheckConstraint("token ~ '^[A-Za-z0-9_-]{1,64}$'", name="token_shape"),
        CheckConstraint("expiry IN ('never', '7d', '30d', '90d')", name="expiry_known"),
        Index("uq_meeting_result_shares_token", "token", unique=True),
        Index("ix_meeting_result_shares_user", "user_id"),
    )

    session_id: Mapped[UUID] = meeting_reference(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    token: Mapped[str] = mapped_column(Text)
    show_transcript: Mapped[bool] = mapped_column(Boolean, server_default=true())
    show_names: Mapped[bool] = mapped_column(Boolean, server_default=false())
    allow_comments: Mapped[bool] = mapped_column(Boolean, server_default=false())
    expiry: Mapped[str] = mapped_column(Text, server_default="never")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShareCommentRecord(ModelBase):
    """A comment left on a shared page; no id or address of its author is kept."""

    __tablename__ = "meeting_share_comments"
    __table_args__ = (
        CheckConstraint("length(text) BETWEEN 1 AND 2000", name="text_length"),
        # До 60 символов у новых; 64 — у перенесённых из черновика.
        CheckConstraint("length(author) BETWEEN 1 AND 64", name="author_length"),
        Index("ix_meeting_share_comments_page", "session_id", "created_at"),
        Index("ix_meeting_share_comments_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("meeting_result_shares.session_id", ondelete="CASCADE")
    )
    # Владелец встречи, не автор: у автора нет аккаунта.
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    author: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
