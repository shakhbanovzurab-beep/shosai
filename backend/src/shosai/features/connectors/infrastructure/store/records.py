"""Connectors' tables in each home (connectors plan §3.8, ADR 0075).

A grant is one provider account's consent, owned by a person (`org_id` empty) or by a
workspace's installation; its secrets live in a table of their own, so a registry read never
loads a ciphertext; a connection is an app on a grant. Row-level security admits a person's
own personal rows only and a workspace's rows by the company policy (ADR 0053); no foreign
key points at `users` — the account registry erases them. The database keeps the closed sets,
the rule that `needs_reconnect` comes exactly with a problem, one account per app per person,
and connections on grants of the same owner.
"""

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Any, Final
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase
from shosai.features.connectors.domain.catalogue import App, AuthKind, Provider
from shosai.features.connectors.domain.states import ConnectionStatus, GrantStatus, Problem


def closed_set(values: Iterable[StrEnum]) -> str:
    """A closed set of string values for a `CHECK ... IN (...)`."""
    return ", ".join(f"'{value}'" for value in values)


PROVIDERS: Final = closed_set(Provider)
APPS: Final = closed_set(App)
AUTH_KINDS: Final = closed_set(AuthKind)
GRANT_STATUSES: Final = closed_set(GrantStatus)
CONNECTION_STATUSES: Final = closed_set(ConnectionStatus)
PROBLEMS: Final = closed_set(Problem)
LABEL_MAX: Final = 320
ACCOUNT_ID_MAX: Final = 255


def moment(*, nullable: bool = False) -> Mapped[datetime]:
    """A timestamp column; a required one defaults to now."""
    if nullable:
        return mapped_column(DateTime(timezone=True), nullable=True)
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class GrantRecord(ModelBase):
    """One provider account's consent, shared by that account's apps (CN-D2)."""

    __tablename__ = "connector_grants"
    __table_args__ = (
        CheckConstraint(f"provider IN ({PROVIDERS})", name="provider_known"),
        CheckConstraint(f"auth_kind IN ({AUTH_KINDS})", name="auth_kind_known"),
        CheckConstraint(f"status IN ({GRANT_STATUSES})", name="status_known"),
        CheckConstraint(f"problem IS NULL OR problem IN ({PROBLEMS})", name="problem_known"),
        CheckConstraint(
            "(status = 'needs_reconnect') = (problem IS NOT NULL)", name="problem_when_waiting"
        ),
        CheckConstraint("client_key ~ '^[a-z][a-z0-9_]{1,31}$'", name="client_key_format"),
        CheckConstraint(
            f"char_length(external_account_id) BETWEEN 1 AND {ACCOUNT_ID_MAX}",
            name="external_account_id_length",
        ),
        CheckConstraint(
            f"account_label IS NULL OR char_length(account_label) <= {LABEL_MAX}",
            name="account_label_length",
        ),
        CheckConstraint("consecutive_failures >= 0", name="failures_counted"),
        # Цель составного ключа подключений: приложение на гранте того же владельца.
        UniqueConstraint("id", "user_id", name="uq_connector_grants_id_user_id"),
        Index(
            "uq_connector_grants_personal_account",
            "user_id", "provider", "client_key", "external_account_id",
            unique=True, postgresql_where=text("org_id IS NULL"),
        ),
        Index(
            "uq_connector_grants_workspace_account",
            "org_id", "provider", "external_account_id",
            unique=True, postgresql_where=text("org_id IS NOT NULL"),
        ),
    )  # fmt: skip

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    provider: Mapped[str] = mapped_column(Text)
    client_key: Mapped[str] = mapped_column(Text)
    auth_kind: Mapped[str] = mapped_column(Text)
    external_account_id: Mapped[str] = mapped_column(Text)
    account_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    provider_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    status: Mapped[str] = mapped_column(Text, server_default=GrantStatus.ACTIVE.value)
    problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, server_default="0")
    last_failure_at: Mapped[datetime | None] = moment(nullable=True)
    created_at: Mapped[datetime] = moment()
    updated_at: Mapped[datetime] = moment()


class GrantSecretRecord(ModelBase):
    """A grant's ciphertexts under core's Fernet key ring, and its refresh lease."""

    __tablename__ = "connector_grant_secrets"
    __table_args__ = (
        CheckConstraint(
            "access_token_enc IS NOT NULL OR refresh_token_enc IS NOT NULL "
            "OR secret_enc IS NOT NULL",
            name="something_held",
        ),
        CheckConstraint("refresh_generation >= 0", name="generation_counted"),
        ForeignKeyConstraint(
            ["grant_id", "user_id"], ["connector_grants.id", "connector_grants.user_id"],
            name="fk_connector_grant_secrets_grant", ondelete="CASCADE",
        ),
        Index(
            "ix_connector_grant_secrets_keepalive_at", "keepalive_at",
            postgresql_where=text("keepalive_at IS NOT NULL"),
        ),
    )  # fmt: skip

    grant_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # Пароль приложения, ключ API или адрес Catch Hook.
    secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    expires_at: Mapped[datetime | None] = moment(nullable=True)
    refresh_generation: Mapped[int] = mapped_column(Integer, server_default="0")
    refreshing_until: Mapped[datetime | None] = moment(nullable=True)
    refreshed_at: Mapped[datetime | None] = moment(nullable=True)
    keepalive_at: Mapped[datetime | None] = moment(nullable=True)


class ConnectionRecord(ModelBase):
    """An app on a grant, for its person or its workspace."""

    __tablename__ = "connections"
    __table_args__ = (
        CheckConstraint(f"app IN ({APPS})", name="app_known"),
        CheckConstraint(f"status IN ({CONNECTION_STATUSES})", name="status_known"),
        CheckConstraint(f"problem IS NULL OR problem IN ({PROBLEMS})", name="problem_known"),
        CheckConstraint(
            "(status = 'needs_reconnect') = (problem IS NOT NULL)", name="problem_when_waiting"
        ),
        ForeignKeyConstraint(
            ["grant_id", "user_id"], ["connector_grants.id", "connector_grants.user_id"],
            name="fk_connections_grant",
        ),
        Index(
            "uq_connections_personal_app", "user_id", "app",
            unique=True, postgresql_where=text("org_id IS NULL"),
        ),
        Index(
            "uq_connections_workspace_app", "org_id", "app", "grant_id",
            unique=True, postgresql_where=text("org_id IS NOT NULL"),
        ),
        Index("ix_connections_grant_id", "grant_id"),
    )  # fmt: skip

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    app: Mapped[str] = mapped_column(Text)
    grant_id: Mapped[UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(Text, server_default=ConnectionStatus.ACTIVE.value)
    problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[datetime | None] = moment(nullable=True)
    connected_at: Mapped[datetime] = moment()
    created_at: Mapped[datetime] = moment()
    updated_at: Mapped[datetime] = moment()


CONNECTOR_MODELS: Final = (GrantRecord, GrantSecretRecord, ConnectionRecord)
