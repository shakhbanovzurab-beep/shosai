"""Image tokens in cost rows (every home): the tokens of pictures given and made.

OpenRouter prices its image models per image token, the pictures a call is given and the one
it makes apart (`image_token`, `image_output`), so a row keeps both, as it keeps audio
tokens. The new units are admitted where a row names its unit, the same set as the price
list's.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "0af60aefe97a"
down_revision: str | None = "e2015859a9a7"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

UNIT = "ck_provider_costs_unit_known"
UNITS = (
    "unit IS NULL OR unit IN ('input_token', 'cached_input_token', 'output_token', "
    "'input_audio_token', 'output_audio_token', 'input_image_token', 'output_image_token', "
    "'audio_second', 'page', 'document', 'request', 'image')"
)
FORMER_UNITS = (
    "unit IS NULL OR unit IN ('input_token', 'cached_input_token', 'output_token', "
    "'input_audio_token', 'output_audio_token', 'audio_second', 'page', 'document', "
    "'request', 'image')"
)
IMAGE = "ck_provider_costs_image_tokens_not_negative"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Add the image token columns and admit the image token units."""
    for column in ("input_image_tokens", "output_image_tokens"):
        op.add_column(
            "provider_costs", sa.Column(column, sa.Integer(), server_default="0", nullable=False)
        )
    op.create_check_constraint(
        op.f(IMAGE), "provider_costs", "input_image_tokens >= 0 AND output_image_tokens >= 0"
    )
    op.drop_constraint(op.f(UNIT), "provider_costs", type_="check")
    op.create_check_constraint(op.f(UNIT), "provider_costs", UNITS)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the image token columns; rows keep their cost in USD and RUB."""
    op.drop_constraint(op.f(UNIT), "provider_costs", type_="check")
    op.create_check_constraint(op.f(UNIT), "provider_costs", FORMER_UNITS)
    op.drop_constraint(op.f(IMAGE), "provider_costs", type_="check")
    for column in ("output_image_tokens", "input_image_tokens"):
        op.drop_column("provider_costs", column)
