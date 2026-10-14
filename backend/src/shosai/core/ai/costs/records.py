"""One row per paid model call, in the payer's home (§8.1 "Cost", inv-9, ADR 0035, ADR 0041).

A row is written once per effect key, in the transaction the effect-key ledger opens for it,
with the call's units in typed columns and its cost in USD — the provider's reported amount
or units times the prices in force at `created_at` — and in RUB at the rate of the moment.
Monthly partitions on `created_at`, kept 5 years (402-FZ); core's upkeep drops older ones.

No row-level security, like the outbox: reports sum every company of a home, and the
application reaches the table only through `core/ai`. The row holds ids, units and money,
never a prompt, an answer or a name.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.ai.pricing.records import UNITS_CHECK
from shosai.core.db.model_base import ModelBase
from shosai.core.db.partitions.policy import monthly_partition_range

# Виды вызовов: речь и живые сессии добавил шаг 3 F6 (a1c4e9d27b53), решения и OCR — шаг 4
# (e7a1c4d9b2f6).
KINDS_CHECK = (
    "kind IN ('chat', 'embed', 'rerank', 'image', 'transcribe', 'diarize', "
    "'live_transcription', 'live_translation', 'voice', 'decide', 'ocr')"
)


class ProviderCost(ModelBase):
    """What one model call cost, who pays for it and why it was made."""

    __tablename__ = "provider_costs"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_provider_costs"),
        CheckConstraint(
            "(payer = 'user' AND user_id IS NOT NULL AND platform_account IS NULL) OR "
            "(payer = 'platform' AND user_id IS NULL AND platform_account IS NOT NULL)",
            name="payer_named",
        ),
        CheckConstraint(
            "platform_account IN ('landing_demo', 'help_assistant', 'system')",
            name="platform_account_known",
        ),
        CheckConstraint("call_class IN ('essential', 'standard', 'expensive')", name="class_known"),
        CheckConstraint("origin IN ('interactive', 'background', 'system')", name="origin_known"),
        CheckConstraint(KINDS_CHECK, name="kind_known"),
        CheckConstraint("outcome IN ('ok', 'failed')", name="outcome_known"),
        CheckConstraint(
            "cost_source IN ('reported', 'priced', 'draft_session')", name="source_known"
        ),
        CheckConstraint(f"unit IS NULL OR {UNITS_CHECK}", name="unit_known"),
        CheckConstraint(
            "input_tokens >= 0 AND cached_tokens >= 0 AND output_tokens >= 0 AND units >= 0 "
            "AND cost_usd >= 0",
            name="amounts_not_negative",
        ),
        CheckConstraint(
            "input_audio_tokens >= 0 AND output_audio_tokens >= 0",
            name="audio_tokens_not_negative",
        ),
        CheckConstraint(
            "(exchange_rate_used IS NULL) = (cost_rub IS NULL)", name="rubles_with_their_rate"
        ),
        CheckConstraint("length(effect_key) BETWEEN 1 AND 200", name="effect_key_length"),
        Index("ix_provider_costs_user", "user_id", "created_at"),
        Index("ix_provider_costs_model", "provider", "model", "created_at"),
        # Сверка считает строки часа дома: BRIN по времени вместо скана партиции месяца.
        Index(
            "ix_provider_costs_created_brin",
            "created_at",
            postgresql_using="brin",
            postgresql_with={"autosummarize": "on"},
        ),
        {"postgresql_partition_by": monthly_partition_range("created_at")},
    )

    id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    effect_key: Mapped[str] = mapped_column(Text)
    payer: Mapped[str] = mapped_column(Text)
    platform_account: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[UUID | None] = mapped_column(Uuid)
    org_id: Mapped[UUID | None] = mapped_column(Uuid)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    feature: Mapped[str] = mapped_column(Text)
    call_class: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    cached_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    input_audio_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    output_audio_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    units: Mapped[Decimal] = mapped_column(Numeric(18, 3), server_default="0")
    unit: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 10))
    cost_source: Mapped[str] = mapped_column(Text)
    exchange_rate_used: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    cost_rub: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
