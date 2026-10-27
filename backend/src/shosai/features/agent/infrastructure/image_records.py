"""The operator's pictures and the objects they leave behind (revision `173ed4677079`).

`agent_images` points at each picture's object, by the run that drew it; a deleted row puts its
key into `agent_image_releases` by a trigger in the same transaction, so a thread's deletion,
whatever path it takes, leaves the object for the release tick to delete. Both are personal by
row-level security; the sweep role reads and empties the releases.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.agent.domain.images import BYTES_MAX, IMAGE_TYPES

TYPES: Final = ", ".join(f"'{kind}'" for kind in sorted(IMAGE_TYPES))


class AgentImageRecord(ModelBase):
    """A picture the operator's Leo drew: its object and its size."""

    __tablename__ = "agent_images"
    __table_args__ = (
        CheckConstraint(f"content_type IN ({TYPES})", name="type_known"),
        CheckConstraint(f"size_bytes BETWEEN 1 AND {BYTES_MAX}", name="size_range"),
        CheckConstraint("width > 0 AND height > 0", name="dimensions_positive"),
        Index("ix_agent_images_run", "user_id", "run_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[UUID] = mapped_column(Uuid)
    run_id: Mapped[UUID] = mapped_column(Uuid)
    object_key: Mapped[str] = mapped_column(Text, unique=True)
    content_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)


class AgentImageReleaseRecord(ModelBase):
    """The object of a deleted picture, waiting to be deleted from the bucket."""

    __tablename__ = "agent_image_releases"

    object_key: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


IMAGE_MODELS: Final = (AgentImageRecord, AgentImageReleaseRecord)
