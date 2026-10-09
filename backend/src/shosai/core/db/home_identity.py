"""The one-row table that names the home a database belongs to (F1 plan §3.6).

The first migration writes it in every home. A process compares it with the home it was
configured for, so swapped addresses stop the start instead of mixing two jurisdictions.
"""

from sqlalchemy import Boolean, CheckConstraint, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase, table_info


class HomeIdentity(ModelBase):
    """The home of this database; exactly one row."""

    __tablename__ = "home_identity"
    __table_args__ = (
        CheckConstraint("singleton", name="singleton"),
        CheckConstraint("home IN ('ru', 'eu')", name="known_home"),
        {"info": table_info(seeded_by_migration=True)},
    )

    singleton: Mapped[bool] = mapped_column(Boolean, primary_key=True, server_default=true())
    home: Mapped[str] = mapped_column(Text)
