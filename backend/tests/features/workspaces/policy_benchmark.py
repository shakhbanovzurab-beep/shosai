"""What the access policy and RLS cost at the design point (workspaces plan §3.5, §22 gate).

Not collected by a normal run: `uv run pytest tests/features/workspaces/policy_benchmark.py`.
It writes 100 workspaces of 30 members with three teams each and a million rows of the
probe meeting resource — half of them a workspace's (at every level, selected rows with a
team and a member grant), half personal, a sixth of those shared into the owner's
workspace — then compares the server's execution time (`EXPLAIN ANALYZE`) of three reads:
one row by id, a workspace screen's 50 newest rows, and 50 newest rows across every space
of the person, as Leo reads. Each read runs bare, with the policy's predicate as the
tables' owner (no RLS), and with the predicate as the application role (RLS too). The
results are logged; the plan records them.
"""

import hashlib
import statistics
import uuid
from collections.abc import Awaitable, Callable

import sqlalchemy as sa
import structlog

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.workspaces.contracts import Viewer
from tests.features.workspaces.probe_resources import NOTES
from tests.features.workspaces.test_access_policy import policy
from tests.harness.connections import Connection, fetch_value
from tests.harness.database_access import DatabaseAccess
from tests.harness.run_slot import RunSlot

RUNS = 25
# Перед запросом, собранным SQLAlchemy из констант бенчмарка; ввода извне нет.
EXPLAIN = "EXPLAIN (ANALYZE, FORMAT JSON) "
HOME = Home.RU
SELECTED_ROWS = " FROM generate_series(1, 1000000) n WHERE n % 2 = 1 AND n % 5 IN (2, 3)"
SEED = (
    # Пространства, участники (1 — владелец, 2–3 — админы, 30 — гость), команды.
    "INSERT INTO organizations (id, slug, name, created_by) SELECT md5('o' || g)::uuid,"
    " 'bench-' || g, 'Bench', md5('u' || g || '-1')::uuid FROM generate_series(1, 100) g",
    "INSERT INTO memberships (id, org_id, user_id, role) SELECT md5('m' || g || '-' || i)::uuid,"
    " md5('o' || g)::uuid, md5('u' || g || '-' || i)::uuid, CASE WHEN i = 1 THEN 'owner'"
    " WHEN i <= 3 THEN 'admin' WHEN i = 30 THEN 'guest' ELSE 'member' END"
    " FROM generate_series(1, 100) g, generate_series(1, 30) i",
    "INSERT INTO teams (id, org_id, name, color) SELECT md5('t' || g || '-' || t)::uuid,"
    " md5('o' || g)::uuid, 'team', 'sky' FROM generate_series(1, 100) g, generate_series(0, 2) t",
    "INSERT INTO team_members (team_id, membership_id, org_id)"
    " SELECT md5('t' || g || '-' || i % 3)::uuid, md5('m' || g || '-' || i)::uuid,"
    " md5('o' || g)::uuid FROM generate_series(1, 100) g, generate_series(1, 30) i",
    # Строки: нечётные — пространства (уровень по n % 5), чётные — личные.
    "INSERT INTO probe_meetings (id, user_id, org_id, access) SELECT md5('r' || n)::uuid,"
    " md5('u' || (n % 100 + 1) || '-' || (n % 29 + 1))::uuid,"
    " CASE WHEN n % 2 = 1 THEN md5('o' || (n % 100 + 1))::uuid END,"
    " CASE WHEN n % 2 = 1 THEN (ARRAY['organization', 'organization', 'selected', 'selected',"
    " 'owner'])[n % 5 + 1] END FROM generate_series(1, 1000000) n",
    "INSERT INTO resource_grants (org_id, resource_kind, resource_id, grantee_kind, grantee_id)"
    " SELECT md5('o' || (n % 100 + 1))::uuid, 'meeting', md5('r' || n)::uuid, 'team',"
    " md5('t' || (n % 100 + 1) || '-' || n % 3)::uuid" + SELECTED_ROWS,
    "INSERT INTO resource_grants (org_id, resource_kind, resource_id, grantee_kind, grantee_id)"
    " SELECT md5('o' || (n % 100 + 1))::uuid, 'meeting', md5('r' || n)::uuid, 'member',"
    " md5('m' || (n % 100 + 1) || '-' || (n % 28 + 2))::uuid" + SELECTED_ROWS,
    # Каждая шестая строка (личная) поделена в пространство владельца: каждая вторая — всем,
    # остальные — команде.
    "INSERT INTO workspace_meeting_shares (session_id, org_id, shared_by_membership_id, access)"
    " SELECT md5('r' || n)::uuid, md5('o' || (n % 100 + 1))::uuid,"
    " md5('m' || (n % 100 + 1) || '-' || (n % 29 + 1))::uuid,"
    " CASE WHEN n % 12 = 0 THEN 'organization' ELSE 'selected' END"
    " FROM generate_series(6, 1000000, 6) n",
    "INSERT INTO resource_grants (org_id, resource_kind, resource_id, grantee_kind, grantee_id)"
    " SELECT md5('o' || (n % 100 + 1))::uuid, 'meeting', md5('r' || n)::uuid, 'team',"
    " md5('t' || (n % 100 + 1) || '-' || n % 3)::uuid FROM generate_series(6, 1000000, 6) n"
    " WHERE n % 12 <> 0",
    "ANALYZE organizations, memberships, teams, team_members, probe_meetings,"
    " resource_grants, workspace_meeting_shares",
)
log = structlog.stdlib.get_logger(__name__)


def md5_id(text: str) -> uuid.UUID:
    """The id PostgreSQL's `md5(text)::uuid` gives, to name a seeded row from Python."""
    return uuid.UUID(hashlib.md5(text.encode(), usedforsecurity=False).hexdigest())


# Читатель — участник 5 первого пространства, в команде 2.
VIEWER = md5_id("u1-5")
ORG = md5_id("o1")


def literal(query: sa.Select[tuple[uuid.UUID]], dialect: sa.Dialect) -> str:
    """The query with its values inlined, for EXPLAIN on either connection."""
    return str(query.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))


def execution_ms(plan: object) -> float:
    """The server's execution time of an `EXPLAIN (ANALYZE, FORMAT JSON)` result."""
    if not isinstance(plan, list):
        message = "EXPLAIN вернул не JSON-план"
        raise TypeError(message)
    return float(plan[0]["Execution Time"])


def owner_timer(connection: Connection) -> Callable[[str], Awaitable[float]]:
    async def run(sql: str) -> float:
        return execution_ms(await fetch_value(connection, EXPLAIN + sql))

    return run


def app_timer(homes: DatabaseAccess) -> Callable[[str], Awaitable[float]]:
    async def run(sql: str) -> float:
        scope = TenancyScope(HOME, VIEWER)
        async with homes.transactions.begin(scope, read_only=True) as session:
            return execution_ms(await session.scalar(sa.text(EXPLAIN + sql)))

    return run


async def median(timer: Callable[[str], Awaitable[float]], sql: str) -> float:
    return statistics.median([await timer(sql) for _ in range(RUNS)])


async def test_the_policy_overhead_at_the_design_point(
    homes: DatabaseAccess, probe_resources: None, run_slot: RunSlot
) -> None:
    connection = run_slot.claimed.connections[HOME]
    async with connection.transaction():
        for statement in SEED:
            await connection.execute(statement)
    table, row_id = NOTES.table, NOTES.table.c.id
    one = await fetch_value(
        connection,
        "SELECT id FROM probe_meetings WHERE org_id = %s AND access = 'organization' LIMIT 1",
        (ORG,),
    )
    newest = row_id.desc()
    reads = {
        "one row by id": (sa.select(row_id).where(row_id == one), None),
        "workspace screen, 50": (
            sa.select(row_id).where(table.c.org_id == ORG).order_by(newest).limit(50),
            ORG,
        ),
        "every space, 50": (sa.select(row_id).order_by(newest).limit(50), None),
    }
    owner, app = owner_timer(connection), app_timer(homes)
    dialect = homes.databases.engine(HOME).dialect
    for name, (bare, within) in reads.items():
        guarded = bare.where(policy().readable(NOTES, Viewer(VIEWER, within)))
        bare_ms = await median(owner, literal(bare, dialect))
        policy_ms = await median(owner, literal(guarded, dialect))
        rls_ms = await median(app, literal(guarded, dialect))
        log.info(
            "Замер политики доступа",
            read=name,
            bare_ms=round(bare_ms, 3),
            policy_ms=round(policy_ms, 3),
            policy_rls_ms=round(rls_ms, 3),
            rls_share=round((rls_ms - policy_ms) / rls_ms, 3),
        )
