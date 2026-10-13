"""The effect-key ledger, in every home (target architecture §10, inv-9; F1 audit A9).

A row says that the effect named by `(scope, key)` was applied in this home and keeps a
small reference to its outcome — a run id, a cost id, a membership — so a repeat returns
that outcome instead of applying the effect again. The row is written in the effect's own
transaction: both commit or neither does. It keeps the account and company of that
transaction for the deletion of an account, and expires after the time its scope declares.

Like the outbox, the table has no row-level security: the purge sweeps every tenant of the
home, and the application reaches it only through `core/idempotency`, by the full key,
which the caller derives from its principal (an account id, an action id).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

SCOPE_PATTERN = "^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$"
KEY_MAX_LENGTH = 200
OUTCOME_MAX_BYTES = 8192


class EffectKeyRecord(ModelBase):
    """One applied effect: its key, the fingerprint of its request and its outcome."""

    __tablename__ = "effect_keys"
    __table_args__ = (
        CheckConstraint(f"scope ~ '{SCOPE_PATTERN}' AND length(scope) <= 64", name="scope_format"),
        CheckConstraint(f"length(key) BETWEEN 1 AND {KEY_MAX_LENGTH}", name="key_length"),
        CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="fingerprint_sha256"),
        CheckConstraint(f"pg_column_size(outcome) <= {OUTCOME_MAX_BYTES}", name="outcome_size"),
        CheckConstraint("expires_at > recorded_at", name="expires_after_recorded"),
        # Единственный запрос очистки — по сроку.
        Index("ix_effect_keys_expires_at", "expires_at"),
    )

    scope: Mapped[str] = mapped_column(Text, primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    # SHA-256 запроса: тот же ключ с другим запросом — ошибка клиента, а не повтор.
    fingerprint: Mapped[str | None] = mapped_column(Text)
    # NULL только внутри транзакции эффекта: строку пишут до эффекта, исход — после.
    outcome: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    user_id: Mapped[UUID | None] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
