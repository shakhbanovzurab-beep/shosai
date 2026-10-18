"""Files and folders in each home (revision `e7b2c5d9a314`; ADR 0055).

`storage_files` is shareable: `user_id`, `org_id` and `access` as workspaces' access policy
reads them. Its object key is the full key — legacy draft keys verbatim — and several rows
may share one (FL-D4). A deleted file keeps its row, hidden, for 7 days (FL-D5).
"""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Table,
    Text,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.access.shareable import ShareableResource
from shosai.core.db.model_base import ModelBase


class FileFolderRecord(ModelBase):
    """A person's flat folder."""

    __tablename__ = "file_folders"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 500", name="name_length"),
        Index("ix_file_folders_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(Text)
    leo: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StorageFileRecord(ModelBase):
    """A file of a person or a workspace, pointing at its object."""

    __tablename__ = "storage_files"
    __table_args__ = (
        CheckConstraint("(org_id IS NULL) = (access IS NULL)", name="org_with_access"),
        CheckConstraint(
            "access IS NULL OR access IN ('owner', 'selected', 'organization')",
            name="access_known",
        ),
        CheckConstraint("org_id IS NULL OR folder_id IS NULL", name="folders_personal"),
        CheckConstraint("length(name) BETWEEN 1 AND 500", name="name_length"),
        CheckConstraint("length(content_type) BETWEEN 1 AND 255", name="type_length"),
        CheckConstraint("size_bytes >= 0", name="size_not_negative"),
        CheckConstraint("length(object_key) BETWEEN 1 AND 1024", name="key_length"),
        CheckConstraint("sha256 IS NULL OR octet_length(sha256) = 32", name="sha256_length"),
        Index("ix_storage_files_user", "user_id"),
        Index("ix_storage_files_org", "org_id"),
        Index("ix_storage_files_folder", "folder_id"),
        Index("ix_storage_files_object_key", "object_key"),
        Index(
            "ix_storage_files_hidden",
            "deleted_at",
            postgresql_where=text("deleted_at IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    access: Mapped[str | None] = mapped_column(Text)
    folder_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("file_folders.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    object_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[bytes | None] = mapped_column(LargeBinary)
    starred: Mapped[bool] = mapped_column(Boolean, server_default=false())
    leo_on: Mapped[bool] = mapped_column(Boolean, server_default=false())
    # Leo не читает файл даже через папку, пока человек сам его не включит (FL-D10).
    leo_held: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Аккаунт владельца в окне удаления: файл не отдаётся никому (ADR 0045, пункт 6).
    account_hidden: Mapped[bool] = mapped_column(Boolean, server_default=false())
    # Удалённый файл скрыт 7 дней и не входит в квоту (FL-D5).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Вид ресурса для политики доступа workspaces: личный файл публикуется записью «personal».
FILE_RESOURCE = ShareableResource("file", cast("Table", StorageFileRecord.__table__))
