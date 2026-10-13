"""Audio tokens of live models in cost rows (every home, F6 step 3b).

Live models price audio tokens apart from text ones, so a row keeps both. The new units are
admitted where a row names its unit, the same set as the price list's.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "c3d8f1a0b6e4"
down_revision: str | None = "b7e2f05c9d18"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

UNIT = "ck_provider_costs_unit_known"
UNITS = (
    "unit IS NULL OR unit IN ('input_token', 'cached_input_token', 'output_token', "
    "'input_audio_token', 'output_audio_token', 'audio_second', 'page', 'document', "
    "'request', 'image')"
)
FORMER_UNITS = (
    "unit IS NULL OR unit IN ('input_token', 'cached_input_token', 'output_token', "
    "'audio_second', 'page', 'document', 'request', 'image')"
)
AUDIO = "ck_provider_costs_audio_tokens_not_negative"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the audio token columns and admit the audio token units."""
    for column in ("input_audio_tokens", "output_audio_tokens"):
        op.add_column(
            "provider_costs", sa.Column(column, sa.Integer(), server_default="0", nullable=False)
        )
    op.create_check_constraint(
        op.f(AUDIO), "provider_costs", "input_audio_tokens >= 0 AND output_audio_tokens >= 0"
    )
    op.drop_constraint(op.f(UNIT), "provider_costs", type_="check")
    op.create_check_constraint(op.f(UNIT), "provider_costs", UNITS)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the audio token columns; rows keep their cost in USD and RUB."""
    op.drop_constraint(op.f(UNIT), "provider_costs", type_="check")
    op.create_check_constraint(op.f(UNIT), "provider_costs", FORMER_UNITS)
    op.drop_constraint(op.f(AUDIO), "provider_costs", type_="check")
    for column in ("output_audio_tokens", "input_audio_tokens"):
        op.drop_column("provider_costs", column)
