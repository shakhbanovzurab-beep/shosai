"""Identity's tables (identity plan §3.5; DATA_MAPPING §5.1).

`users`, `user_consents` and `pending_registrations` exist in every home and hold the
person's data there; `directory_entries` exists only in the EU home and holds nothing
personal: the address's HMAC, the account id, its home and its state (§6, nfr-4).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase, table_info
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.core.kernel.homes import Home

ACCOUNT_STATES = (
    "'active', 'frozen', 'banned', 'deletion_scheduled', 'deleting', 'transferring', 'deleted'"
)
DIRECTORY_STATES = (
    "'claimed', 'active', 'frozen', 'banned', 'deletion_scheduled', 'transferring', 'deleted'"
)
CONSENT_KINDS = "'personal_data', 'cross_border', 'marketing', 'improve_models', 'share_location'"
LANGUAGES = ", ".join(f"'{code}'" for code in SUPPORTED_LANGUAGES)


class User(ModelBase):
    """An account in its home: who the person is and how they sign in."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"state IN ({ACCOUNT_STATES})", name="state_known"),
        CheckConstraint("length(email) BETWEEN 3 AND 254", name="email_length"),
        CheckConstraint("length(full_name) BETWEEN 1 AND 80", name="full_name_length"),
        CheckConstraint(
            "display_name IS NULL OR length(display_name) BETWEEN 1 AND 80",
            name="display_name_length",
        ),
        CheckConstraint("country IS NULL OR country ~ '^[A-Z]{2}$'", name="country_code"),
        CheckConstraint(f"language IN ({LANGUAGES})", name="language_known"),
        CheckConstraint("token_version >= 0", name="token_version_not_negative"),
        Index("uq_users_email", "email", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    # Пусто у аккаунта только со входом через соцсеть.
    password_hash: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    work_role: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str | None] = mapped_column(Text)
    avatar_key: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="active")
    token_version: Mapped[int] = mapped_column(Integer, server_default="0")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserConsent(ModelBase):
    """One change of one consent: the journal is append-only, the latest row is current."""

    __tablename__ = "user_consents"
    __table_args__ = (
        CheckConstraint(f"kind IN ({CONSENT_KINDS})", name="kind_known"),
        CheckConstraint("source IN ('registration', 'settings', 'migration')", name="source_known"),
        CheckConstraint(
            "user_agent IS NULL OR length(user_agent) <= 512", name="user_agent_length"
        ),
        Index("ix_user_consents_current", "user_id", "kind", "recorded_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    granted: Mapped[bool] = mapped_column(Boolean)
    version: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PendingRegistration(ModelBase):
    """A registration waiting for its code, in the home of the country the person chose."""

    __tablename__ = "pending_registrations"
    __table_args__ = (
        CheckConstraint("attempts BETWEEN 0 AND 5", name="attempts_bounded"),
        CheckConstraint("resends BETWEEN 0 AND 3", name="resends_bounded"),
        CheckConstraint("length(email_hmac) = 32", name="email_hmac_length"),
        CheckConstraint("country ~ '^[A-Z]{2}$'", name="country_code"),
        CheckConstraint("length(full_name) BETWEEN 1 AND 80", name="full_name_length"),
        CheckConstraint(f"language IN ({LANGUAGES})", name="language_known"),
        Index("ix_pending_registrations_expires", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    email_hmac: Mapped[bytes] = mapped_column(LargeBinary)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text)
    consent_cross_border: Mapped[bool] = mapped_column(Boolean)
    consent_marketing: Mapped[bool] = mapped_column(Boolean)
    consent_ip: Mapped[str | None] = mapped_column(INET)
    consent_user_agent: Mapped[str | None] = mapped_column(Text)
    code_hash: Mapped[bytes] = mapped_column(LargeBinary)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    resends: Mapped[int] = mapped_column(Integer, server_default="0")
    # Назначается при первом верном коде: повтор подтверждения занимает каталог тем же id.
    user_id: Mapped[UUID | None] = mapped_column(Uuid)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DirectoryEntry(ModelBase):
    """Where an address's account lives: the only trace of it outside its home (§6)."""

    __tablename__ = "directory_entries"
    __table_args__ = (
        CheckConstraint(f"state IN ({DIRECTORY_STATES})", name="state_known"),
        CheckConstraint("home IN ('ru', 'eu')", name="home_known"),
        CheckConstraint("length(email_hmac) = 32", name="email_hmac_length"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("uq_directory_entries_user", "user_id", unique=True),
        Index(
            "ix_directory_entries_claimed", "updated_at", postgresql_where=text("state = 'claimed'")
        ),
        {"info": table_info(homes=(Home.EU,))},
    )

    email_hmac: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    home: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserIdentity(ModelBase):
    """A social account linked to the person: the provider and its stable user id."""

    __tablename__ = "user_identities"
    __table_args__ = (
        CheckConstraint("provider IN ('yandex', 'vk', 'google', 'github')", name="provider_known"),
        CheckConstraint("length(subject) BETWEEN 1 AND 256", name="subject_length"),
        Index("uq_user_identities_subject", "provider", "subject", unique=True),
        Index("uq_user_identities_user", "user_id", "provider", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    email_verified_by_provider: Mapped[bool] = mapped_column(Boolean)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


IDENTITY_MODELS = (User, UserConsent, PendingRegistration, DirectoryEntry, UserIdentity)
