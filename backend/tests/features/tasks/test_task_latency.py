"""A list of tasks and Today within §16.3 on a seeded home (tasks step 3a).

The home holds 3 000 tasks of one person — a third done, a sixth in a workspace the person
is in, assigned to them — among 5 000 tasks of others, half of them in a workspace the
person is not in; every other task has a checklist of three lines and every third two
comments, which each card counts. Through the app, a first page, a deep page, a
workspace's page and Today each answer within the cabinet's read objective: p95 at most
300 ms.
"""

import statistics
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Final

import httpx

from shosai.core.kernel.homes import Home
from tests.features.tasks.task_bench import TaskBench, bearer
from tests.harness.connections import Connection
from tests.harness.run_slot import RunSlot

OBJECTIVE: Final = 0.3
SAMPLES: Final = 40
OWN: Final = 3_000
OTHERS: Final = 5_000
SEED: Final = """
INSERT INTO tasks (id, user_id, org_id, access, title, status, completed_at, due_on,
                   assignee_user_id, created_at, updated_at)
SELECT md5('t' || g)::uuid,
       CASE WHEN g <= %(own)s THEN %(person)s::uuid ELSE md5('u' || (g %% 400))::uuid END,
       CASE WHEN g <= %(own)s AND g %% 6 = 0 THEN %(mine)s::uuid
            WHEN g > %(own)s AND g %% 2 = 0 THEN %(theirs)s::uuid END,
       CASE WHEN (g <= %(own)s AND g %% 6 = 0) OR (g > %(own)s AND g %% 2 = 0)
            THEN 'organization' END,
       'Задача ' || g,
       CASE WHEN g %% 3 = 0 THEN 'done' ELSE 'todo' END,
       CASE WHEN g %% 3 = 0 THEN now() - (g %% 90) * interval '1 day' END,
       CASE WHEN g %% 5 = 0 THEN NULL ELSE current_date + (g %% 60 - 30) END,
       CASE WHEN g <= %(own)s AND g %% 6 = 0 THEN %(person)s::uuid END,
       now() - g * interval '1 minute', now() - g * interval '1 minute'
FROM generate_series(1, %(own)s + %(others)s) AS g
"""
THREADS: Final = """
INSERT INTO task_subtasks (id, task_id, user_id, org_id, title, done, rank)
SELECT gen_random_uuid(), t.id, t.user_id, t.org_id, 'Пункт ' || n, n = 1, chr(64 + n)
FROM tasks AS t CROSS JOIN generate_series(1, 3) AS n
WHERE get_byte(uuid_send(t.id), 15) % 2 = 0;
INSERT INTO task_comments (id, task_id, user_id, org_id, author_user_id, body)
SELECT gen_random_uuid(), t.id, t.user_id, t.org_id, t.user_id, 'Комментарий ' || n
FROM tasks AS t CROSS JOIN generate_series(1, 2) AS n
WHERE get_byte(uuid_send(t.id), 15) % 3 = 0
"""


async def seed(connection: Connection, person: uuid.UUID) -> uuid.UUID:
    """The seeded home with the person's workspace and a stranger's; the person's workspace."""
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    async with connection.transaction():
        for org, owner in ((mine, person), (theirs, uuid.uuid4())):
            await connection.execute(
                "INSERT INTO organizations (id, slug, name, created_by, state)"
                " VALUES (%s, %s, 'w', %s, 'active')",
                (org, f"w-{org.hex[:12]}", owner),
            )
            await connection.execute(
                "INSERT INTO memberships (id, org_id, user_id, role, state)"
                " VALUES (%s, %s, %s, 'owner', 'active')",
                (uuid.uuid4(), org, owner),
            )
        params = {"own": OWN, "others": OTHERS, "person": person, "mine": mine, "theirs": theirs}
        await connection.execute(SEED, params)
        for statement in THREADS.split(";"):
            await connection.execute(statement)
        await connection.execute("ANALYZE tasks, task_subtasks, task_comments")
    return mine


async def p95(call: Callable[[], Awaitable[httpx.Response]]) -> float:
    """The 95th percentile of the call's latency over the samples, after a warm-up."""
    for _ in range(3):
        assert (await call()).status_code == 200
    took: list[float] = []
    for _ in range(SAMPLES):
        started = time.perf_counter()
        answer = await call()
        took.append(time.perf_counter() - started)
        assert answer.status_code == 200, answer.text
    return statistics.quantiles(took, n=20)[-1]


async def test_lists_and_today_answer_within_the_objective(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    person = uuid.uuid4()
    workspace = await seed(run_slot.claimed.connections[Home.EU], person)
    http, headers = task_bench.http, bearer(person)
    deep = (await http.get("/v1/tasks", params={"limit": 200}, headers=headers)).json()
    cursor = deep["next_cursor"]

    first_page = await p95(lambda: http.get("/v1/tasks", headers=headers))
    deep_page = await p95(lambda: http.get("/v1/tasks", params={"cursor": cursor}, headers=headers))
    in_workspace = await p95(
        lambda: http.get("/v1/tasks", params={"workspace_id": str(workspace)}, headers=headers)
    )
    today = await p95(lambda: http.get("/v1/tasks/today", headers=headers))

    assert max(first_page, deep_page, in_workspace, today) <= OBJECTIVE, (
        first_page, deep_page, in_workspace, today,
    )  # fmt: skip
