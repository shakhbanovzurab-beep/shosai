"""Alembic environment: run the one history on the home the runner connected (ADR 0010).

Only `whisperer.core.db.migrations` starts it: the runner passes the migration-role
connection, the home and the application role, and the models' metadata. Each revision
runs in its own transaction and receives the `MigrationScope` of the home.
"""

from alembic import context
from sqlalchemy import Connection, MetaData

from whisperer.core.db.migration_scope import MigrationScope
from whisperer.core.db.migrations import (
    CONNECTION_ATTRIBUTE,
    METADATA_ATTRIBUTE,
    TARGET_ATTRIBUTE,
    MigrationTarget,
)
from whisperer.core.db.model_base import metadata_for_home


def run_home_migrations() -> None:
    """Configure the context for the runner's home and run the requested revisions."""
    if context.is_offline_mode():
        message = "миграции выполняются только по соединению: SQL-скрипты не поддерживаются"
        raise RuntimeError(message)
    attributes = context.config.attributes
    connection: Connection = attributes[CONNECTION_ATTRIBUTE]
    target: MigrationTarget = attributes[TARGET_ATTRIBUTE]
    metadata: MetaData = attributes[METADATA_ATTRIBUTE]
    context.configure(
        connection=connection,
        target_metadata=metadata_for_home(metadata, target.home),
        transaction_per_migration=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations(
            scope=MigrationScope(home=target.home, application_role=target.application_role)
        )


run_home_migrations()
