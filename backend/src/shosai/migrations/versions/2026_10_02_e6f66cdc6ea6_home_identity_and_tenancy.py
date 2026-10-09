"""Home identity, tenancy functions and the application's read of the revision."""

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import (
    EVERY_HOME,
    MigrationScope,
    grant_to_application,
    revoke_from_application,
    runs_in,
)

revision: str = "e6f66cdc6ea6"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None
applies_to = EVERY_HOME

# Функции читают настройки, которые HomeTransactions ставит первой командой транзакции;
# пустая строка и отсутствие настройки — NULL. Без SET search_path, чтобы планировщик
# мог встроить функцию; имя из pg_catalog указано явно.
CREATE_TENANCY_FUNCTIONS = (
    "CREATE FUNCTION app_user_id() RETURNS uuid LANGUAGE sql STABLE PARALLEL SAFE "
    "AS $$ SELECT nullif(pg_catalog.current_setting('app.user_id', true), '')::uuid $$",
    "CREATE FUNCTION app_org_id() RETURNS uuid LANGUAGE sql STABLE PARALLEL SAFE "
    "AS $$ SELECT nullif(pg_catalog.current_setting('app.org_id', true), '')::uuid $$",
)
DROP_TENANCY_FUNCTIONS = ("DROP FUNCTION app_org_id()", "DROP FUNCTION app_user_id()")


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Name the home of the database and give row-level security the tenancy of a transaction."""
    home_identity = op.create_table(
        "home_identity",
        sa.Column("singleton", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("home", sa.Text(), nullable=False),
        sa.CheckConstraint("singleton", name=op.f("ck_home_identity_singleton")),
        sa.CheckConstraint("home IN ('ru', 'eu')", name=op.f("ck_home_identity_known_home")),
        sa.PrimaryKeyConstraint("singleton", name=op.f("pk_home_identity")),
    )
    op.bulk_insert(home_identity, [{"home": scope.home.value}])
    grant_to_application(scope, "home_identity", ("SELECT",))
    # Процесс при старте сверяет ревизию дома со своей историей под ролью приложения.
    grant_to_application(scope, "alembic_version", ("SELECT",))
    for statement in CREATE_TENANCY_FUNCTIONS:
        op.execute(statement)


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Remove the tenancy functions, the revision read and the home identity."""
    for statement in DROP_TENANCY_FUNCTIONS:
        op.execute(statement)
    revoke_from_application(scope, "alembic_version")
    op.drop_table("home_identity")
