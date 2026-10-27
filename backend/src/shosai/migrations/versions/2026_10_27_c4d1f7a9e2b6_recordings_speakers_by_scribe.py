"""Recordings transcribed with speakers by Scribe; pyannote removed (ADR 0073, notes step 29).

In every home, `meeting_processing_runs.turns_key` goes and so does the `diarize` record in
every run's stage state, since no run has that stage any more: a run that was at it goes on
to align. In the EU home, where prices live, the pyannote price rows are deleted with the
provider and `elevenlabs/scribe-v2` gets its seed price: $0.0000611111 per second of audio
(OpenRouter's endpoint list, read on 2026-10-27); OpenRouter reports each call's cost, so
the price admits the model and prices an answer that lost its cost.

The downgrade brings the column back empty and the pyannote seed prices of revision
`b7e2f05c9d18`, and removes Scribe's seed; stage records and operator prices deleted by the
upgrade do not come back.
"""

from decimal import Decimal

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id

revision: str = "c4d1f7a9e2b6"
down_revision: str | None = "ba9f302663d7"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

RUNS = "meeting_processing_runs"
EUR_PER_HOUR_TO_USD_PER_SECOND = Decimal("1.1181") / 3600
PYANNOTE_SEEDS = (
    ("precision-3", Decimal("0.112") * EUR_PER_HOUR_TO_USD_PER_SECOND),
    ("precision-2", Decimal("0.112") * EUR_PER_HOUR_TO_USD_PER_SECOND),
    ("community-1", Decimal("0.035") * EUR_PER_HOUR_TO_USD_PER_SECOND),
)
SCRIBE = ("openrouter", "elevenlabs/scribe-v2", "audio_second", Decimal("0.0000611111111111"))
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


def seed_row(provider: str, model: str, unit: str, price: Decimal) -> dict[str, object]:
    """A seed price in force from now."""
    return {
        "id": new_id(), "provider": provider, "model": model, "unit": unit,
        "price_usd": price.quantize(Decimal("1e-12")), "effective_from": sa.func.now(),
        "source": "seed",
    }  # fmt: skip


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Drop the turns, the diarize records and, in the EU home, pyannote's prices."""
    op.execute(
        sa.text(
            "UPDATE meeting_processing_runs SET stage_state = stage_state - 'diarize' "
            "WHERE stage_state -> 'diarize' IS NOT NULL"
        )
    )
    op.drop_column(RUNS, "turns_key")
    if scope.home is Home.EU:
        op.execute(PRICES.delete().where(PRICES.c.provider == "pyannote"))
        op.execute(PRICES.insert().values([seed_row(*SCRIBE)]))


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Bring the column and pyannote's seed prices back; remove Scribe's seed."""
    op.add_column(RUNS, sa.Column("turns_key", sa.Text(), nullable=True))
    if scope.home is Home.EU:
        provider, model, unit, _ = SCRIBE
        op.execute(
            PRICES.delete().where(
                PRICES.c.provider == provider,
                PRICES.c.model == model,
                PRICES.c.unit == unit,
                PRICES.c.source == "seed",
            )
        )
        op.execute(
            PRICES.insert().values(
                [
                    seed_row("pyannote", model, "audio_second", price)
                    for model, price in PYANNOTE_SEEDS
                ]
            )
        )
