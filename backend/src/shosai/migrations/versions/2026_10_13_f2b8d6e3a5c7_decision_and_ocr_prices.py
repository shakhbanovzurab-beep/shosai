"""Seed prices of Jev and Mistral OCR, checked against the providers' lists (EU home).

OpenRouter (`/api/v1/models`, read on 2026-10-13): typesafe/jev-1.13 $0.042 per million
input tokens, output free. Mistral (`docs.mistral.ai`, OCR 4.1 model card and pricing, read
on 2026-10-13): mistral-ocr-4-1 $4 per 1000 pages. The daily sync keeps OpenRouter's prices
current from then on; Mistral's changes are appended by an operator.
"""

from decimal import Decimal

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import MigrationScope, runs_in
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id

revision: str = "f2b8d6e3a5c7"
down_revision: str | None = "e7a1c4d9b2f6"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

SEEDS = (
    ("openrouter", "typesafe/jev-1.13", "input_token", Decimal("0.000000042")),
    ("openrouter", "typesafe/jev-1.13", "output_token", Decimal(0)),
    ("mistral", "mistral-ocr-4-1", "page", Decimal("0.004")),
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
                 "price_usd": price, "effective_from": sa.func.now(), "source": "seed"}
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
