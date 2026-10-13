"""The price of each model per unit, in the EU home (ADR 0035 point 3).

Append-only: a new price is a new row with a later `effective_from`, never an edit, so the
cost of any past row can be recomputed from the prices in force when it was written. Rows
come from seeds, from the daily OpenRouter sync and from an operator adding a direct
provider's price.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase, table_info
from shosai.core.kernel.homes import Home

# Аудиотокены живых моделей добавил шаг 3b F6 (миграция c3d8f1a0b6e4).
UNITS_CHECK = (
    "unit IN ('input_token', 'cached_input_token', 'output_token', 'input_audio_token', "
    "'output_audio_token', 'audio_second', 'page', 'document', 'request', 'image')"
)


class ProviderPrice(ModelBase):
    """One model's price per unit from a moment on."""

    __tablename__ = "provider_prices"
    __table_args__ = (
        CheckConstraint(UNITS_CHECK, name="unit_known"),
        CheckConstraint("price_usd >= 0", name="price_not_negative"),
        CheckConstraint("source IN ('seed', 'openrouter', 'operator')", name="source_known"),
        CheckConstraint("length(provider) <= 32 AND length(model) <= 128", name="names_length"),
        # Одна цена на модель, единицу и момент; имя — по соглашению проекта.
        UniqueConstraint("provider", "model", "unit", "effective_from"),
        Index("ix_provider_prices_lookup", "provider", "model", "unit", "effective_from"),
        {"info": table_info(homes=(Home.EU,))},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    # Цена за одну единицу: доля цента за токен требует двенадцати знаков.
    price_usd: Mapped[Decimal] = mapped_column(Numeric(20, 12))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
