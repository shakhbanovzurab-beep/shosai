"""Seed prices of the speech models, checked against the providers' lists (EU home).

OpenRouter (`/api/v1/models`, read on 2026-10-13): openai/gpt-4o-transcribe $2.50 and $10
per million input and output tokens, openai/gpt-4o-mini-transcribe $1.25 and $5,
openai/whisper-1 $0.0001 per second of audio. OpenRouter reports the cost of each call, so
these prices admit the models and price a call whose answer lost its cost.

pyannote (`pyannote.ai/pricing`, Developer plan, read on 2026-10-13) prices in euros per
hour of audio: precision-3 and precision-2 €0.112, community-1 €0.035. Converted at the
Central Bank's EUR/USD cross rate of 1.1181 and divided by 3600. An operator who changes the
plan or sees the invoice differ appends a price with source `operator`; seeds are not edited.
"""

from decimal import Decimal

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import MigrationScope, runs_in
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id

revision: str = "b7e2f05c9d18"
down_revision: str | None = "a1c4e9d27b53"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

EUR_PER_HOUR_TO_USD_PER_SECOND = Decimal("1.1181") / 3600
SEEDS = (
    ("openrouter", "openai/gpt-4o-transcribe", "input_token", Decimal("0.0000025")),
    ("openrouter", "openai/gpt-4o-transcribe", "output_token", Decimal("0.00001")),
    ("openrouter", "openai/gpt-4o-mini-transcribe", "input_token", Decimal("0.00000125")),
    ("openrouter", "openai/gpt-4o-mini-transcribe", "output_token", Decimal("0.000005")),
    ("openrouter", "openai/whisper-1", "audio_second", Decimal("0.0001")),
    ("pyannote", "precision-3", "audio_second", Decimal("0.112") * EUR_PER_HOUR_TO_USD_PER_SECOND),
    ("pyannote", "precision-2", "audio_second", Decimal("0.112") * EUR_PER_HOUR_TO_USD_PER_SECOND),
    ("pyannote", "community-1", "audio_second", Decimal("0.035") * EUR_PER_HOUR_TO_USD_PER_SECOND),
)
PRICES = sa.table(
    "provider_prices",
    sa.column("id", sa.Uuid()),
    sa.column("provider", sa.Text()),
    sa.column("model", sa.Text()),
    sa.column("unit", sa.Text()),
    sa.column("price_usd", sa.Numeric(20, 12)),
    sa.column("effective_from", sa.DateTime(timezone=True)),
    sa.column("source", sa.Text()),
)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Append the seed prices, in force from now."""
    op.execute(
        PRICES.insert().values(
            [
                {"id": new_id(), "provider": provider, "model": model, "unit": unit,
                 "price_usd": price.quantize(Decimal("1e-12")), "effective_from": sa.func.now(),
                 "source": "seed"}
                for provider, model, unit, price in SEEDS
            ]
        )
    )  # fmt: skip


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Remove the seed prices this revision appended."""
    for provider, model, unit, _ in SEEDS:
        op.execute(
            PRICES.delete().where(
                PRICES.c.provider == provider,
                PRICES.c.model == model,
                PRICES.c.unit == unit,
                PRICES.c.source == "seed",
            )
        )
