"""Cost rows of decisions and OCR: the kinds of F6 step 4 (every home)."""

from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "e7a1c4d9b2f6"
down_revision: str | None = "d5e2a7c9f4b1"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

NAME = "ck_provider_costs_kind_known"
KINDS = (
    "kind IN ('chat', 'embed', 'rerank', 'image', 'transcribe', 'diarize', "
    "'live_transcription', 'live_translation', 'voice', 'decide', 'ocr')"
)
FORMER_KINDS = (
    "kind IN ('chat', 'embed', 'rerank', 'image', 'transcribe', 'diarize', "
    "'live_transcription', 'live_translation', 'voice')"
)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit decisions and OCR as kinds of cost rows."""
    op.drop_constraint(op.f(NAME), "provider_costs", type_="check")
    op.create_check_constraint(op.f(NAME), "provider_costs", KINDS)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Return to the former kinds; refused while such rows exist, which are kept 5 years."""
    op.drop_constraint(op.f(NAME), "provider_costs", type_="check")
    op.create_check_constraint(op.f(NAME), "provider_costs", FORMER_KINDS)
