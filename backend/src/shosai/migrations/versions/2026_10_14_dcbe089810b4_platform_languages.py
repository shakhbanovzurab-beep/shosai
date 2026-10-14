"""The cabinet's 16 languages become the platform's, in every home (ADR 0046, identity step 6b).

Stored codes move to the cabinet's: `pt` → `pt-BR`, `zh` → `zh-Hant`; Thai is no longer a
platform language and its readers get English. Mails still queued move the same way, so
none fails to render. The accounts and pending registrations then accept only the 16.

The downgrade maps the codes back; Dutch, unknown to the earlier code, becomes English.
"""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import EVERY_HOME, MigrationScope, runs_in

revision: str = "dcbe089810b4"
down_revision: str | None = "9f7ebc9fb893"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

LANGUAGE_TABLES = ("users", "pending_registrations")
LANGUAGES = (
    "'en', 'fr', 'de', 'ru', 'nl', 'it', 'es', 'pt-BR', 'ar', 'tr', 'ko', 'hi', 'vi', "
    "'zh-Hant', 'ja', 'id'"
)
UPGRADE_CODES = (("pt", "pt-BR"), ("zh", "zh-Hant"), ("th", "en"))
DOWNGRADE_CODES = (("pt-BR", "pt"), ("zh-Hant", "zh"), ("nl", "en"))
MOVES = (
    sa.text("UPDATE users SET language = :new WHERE language = :old"),
    sa.text("UPDATE pending_registrations SET language = :new WHERE language = :old"),
    sa.text(
        "UPDATE email_messages SET locale = :new "
        "WHERE locale = :old AND status IN ('queued', 'sending')"
    ),
)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Move the stored codes, then accept only the platform's 16."""
    _move_codes(UPGRADE_CODES)
    for table in LANGUAGE_TABLES:
        op.create_check_constraint(
            op.f(f"ck_{table}_language_known"), table, f"language IN ({LANGUAGES})"
        )


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Drop the constraints and move the codes back."""
    for table in LANGUAGE_TABLES:
        op.drop_constraint(op.f(f"ck_{table}_language_known"), table, type_="check")
    _move_codes(DOWNGRADE_CODES)


def _move_codes(codes: tuple[tuple[str, str], ...]) -> None:
    for old, new in codes:
        for move in MOVES:
            op.execute(move.bindparams(old=old, new=new))
