"""Cost rows of speech calls and live sessions: the kinds of F6 step 3 (every home)."""

from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "a1c4e9d27b53"
down_revision: str | None = "24a8ae5ed316"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

NAME = "ck_provider_costs_kind_known"
KINDS = (
    "kind IN ('chat', 'embed', 'rerank', 'image', 'transcribe', 'diarize', "
    "'live_transcription', 'live_translation', 'voice')"
)
FORMER_KINDS = "kind IN ('chat', 'embed', 'rerank', 'image')"


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit the speech kinds; the check moves to every partition with the parent."""
    op.drop_constraint(op.f(NAME), "provider_costs", type_="check")
    op.create_check_constraint(op.f(NAME), "provider_costs", KINDS)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Return to the former kinds; refused while speech rows exist, which are kept 5 years."""
    op.drop_constraint(op.f(NAME), "provider_costs", type_="check")
    op.create_check_constraint(op.f(NAME), "provider_costs", FORMER_KINDS)
