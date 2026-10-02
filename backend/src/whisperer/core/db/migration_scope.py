"""What a revision knows about the home it runs in, and the helpers it uses (ADR 0010).

The runner passes a `MigrationScope` to `upgrade` and `downgrade`. A revision declares
`applies_to` and wraps both steps with `runs_in(applies_to)`: in another home the step is
skipped while the revision is still stamped, so both homes stay on one revision.
Tables are closed to the application role until a revision grants them explicitly.
"""

import functools
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from alembic import op
from sqlalchemy import DDL

from whisperer.core.kernel.homes import Home

EVERY_HOME: Final = tuple(Home)
COMPANY_ISOLATION_POLICY: Final = "company_isolation"
# Строки без компании — личные ресурсы: их охраняет политика доступа (§7), а RLS отсекает
# строки чужой компании, в том числе от транзакции без компании. Подзапрос вычисляет
# app_org_id() один раз на запрос, а не на каждую строку.
COMPANY_ROWS_VISIBLE: Final = "org_id IS NULL OR org_id = (SELECT app_org_id())"

# Шаблоны DDL: идентификаторы подставляет run_ddl, уже экранированными диалектом.
GRANT: Final = "GRANT %(privileges)s ON TABLE %(table)s TO %(role)s"
REVOKE: Final = "REVOKE ALL ON TABLE %(table)s FROM %(role)s"
ENABLE_ROW_SECURITY: Final = "ALTER TABLE %(table)s ENABLE ROW LEVEL SECURITY"
DISABLE_ROW_SECURITY: Final = "ALTER TABLE %(table)s DISABLE ROW LEVEL SECURITY"
CREATE_COMPANY_POLICY: Final = (
    "CREATE POLICY %(policy)s ON %(table)s "
    f"USING ({COMPANY_ROWS_VISIBLE}) WITH CHECK ({COMPANY_ROWS_VISIBLE})"
)
DROP_POLICY: Final = "DROP POLICY %(policy)s ON %(table)s"

type Privilege = Literal["SELECT", "INSERT", "UPDATE", "DELETE"]
APPLICATION_WRITES: Final[tuple[Privilege, ...]] = ("SELECT", "INSERT", "UPDATE", "DELETE")


@dataclass(frozen=True, slots=True)
class MigrationScope:
    """The home a revision runs in and the role the application connects as there."""

    home: Home
    application_role: str


type MigrationStep = Callable[[MigrationScope], None]


class ScopedStep:
    """An `upgrade` or `downgrade` that runs only in the homes the revision applies to."""

    def __init__(self, step: MigrationStep, applies_to: tuple[Home, ...]) -> None:
        if not applies_to:
            message = "ревизия применяется хотя бы к одному дому"
            raise ValueError(message)
        self.step = step
        self.applies_to = applies_to
        # Имя и описание шага: Alembic пишет их в строку «Running upgrade …» каждой ревизии.
        functools.update_wrapper(self, step)

    def __call__(self, scope: MigrationScope) -> None:
        """Run the step in a home it applies to; elsewhere do nothing."""
        if scope.home in self.applies_to:
            self.step(scope)


def runs_in(applies_to: tuple[Home, ...]) -> Callable[[MigrationStep], ScopedStep]:
    """Decorate `upgrade` and `downgrade` of a revision with its `applies_to`."""

    def decorate(step: MigrationStep) -> ScopedStep:
        return ScopedStep(step, applies_to)

    return decorate


def quote(identifier: str) -> str:
    """A table, function or role name quoted by the dialect of the migration connection."""
    return op.get_bind().dialect.identifier_preparer.quote_identifier(identifier)


def run_ddl(template: str, *, privileges: Sequence[Privilege] = (), **identifiers: str) -> None:
    """Run a DDL template; every identifier is quoted, privileges come from a closed set."""
    context = {name: quote(value) for name, value in identifiers.items()}
    context["privileges"] = ", ".join(privileges)
    op.execute(DDL(template, context=context))


def grant_to_application(
    scope: MigrationScope, table: str, privileges: Sequence[Privilege] = APPLICATION_WRITES
) -> None:
    """Open a table to the application role with exactly these privileges."""
    run_ddl(GRANT, privileges=privileges, table=table, role=scope.application_role)


def revoke_from_application(scope: MigrationScope, table: str) -> None:
    """Close a table to the application role again (the downgrade of a grant)."""
    run_ddl(REVOKE, table=table, role=scope.application_role)


def enable_company_isolation(table: str) -> None:
    """Row-level security on a table with `org_id`: a company's rows only in its scope (§7).

    The application role is subject to it; the migration role owns the table and is not,
    so migrations and their backfills see every row.
    """
    run_ddl(ENABLE_ROW_SECURITY, table=table)
    run_ddl(CREATE_COMPANY_POLICY, table=table, policy=COMPANY_ISOLATION_POLICY)


def disable_company_isolation(table: str) -> None:
    """Remove the company policy and row-level security from a table."""
    run_ddl(DROP_POLICY, table=table, policy=COMPANY_ISOLATION_POLICY)
    run_ddl(DISABLE_ROW_SECURITY, table=table)
