"""Image token units in the price list (EU home), which the daily sync now records.

OpenRouter's `pricing` gives image models a price per image token of the pictures a call is
given (`image_token`) and of the one it makes (`image_output`), read on 2026-10-26; the sync
records them as `input_image_token` and `output_image_token` and a picture is admitted by
the latter. Its downgrade is refused while such prices exist.
"""

from alembic import op

from shosai.core.db.migration_scope import MigrationScope, runs_in
from shosai.core.kernel.homes import Home

revision: str = "6eef9100b25d"
down_revision: str | None = "0af60aefe97a"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

UNIT = "ck_provider_prices_unit_known"
UNITS = (
    "unit IN ('input_token', 'cached_input_token', 'output_token', 'input_audio_token', "
    "'output_audio_token', 'input_image_token', 'output_image_token', 'audio_second', 'page', "
    "'document', 'request', 'image')"
)
FORMER_UNITS = (
    "unit IN ('input_token', 'cached_input_token', 'output_token', 'input_audio_token', "
    "'output_audio_token', 'audio_second', 'page', 'document', 'request', 'image')"
)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit the image token units in the price list."""
    op.drop_constraint(op.f(UNIT), "provider_prices", type_="check")
    op.create_check_constraint(op.f(UNIT), "provider_prices", UNITS)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Return to the former units; refused while an image token price exists."""
    op.drop_constraint(op.f(UNIT), "provider_prices", type_="check")
    op.create_check_constraint(op.f(UNIT), "provider_prices", FORMER_UNITS)
