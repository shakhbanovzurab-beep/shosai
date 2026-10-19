"""The library and a meeting's page within §16.3 on a seeded home (meetings step 7a).

The home holds 2 000 meetings of one person — each with a run, a write-up listing eight
findings, a map and three participants — among 3 000 meetings of others, half of them in
a workspace the person is not in. Through the app, a first page, a deep page and a
meeting's page each answer within the cabinet's read objective: p95 at most 300 ms.
"""

import statistics
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Final

import httpx

from shosai.core.kernel.homes import Home
from tests.features.meetings.library_bench import LibraryBench, bearer
from tests.harness.connections import Connection, fetch_value
from tests.harness.run_slot import RunSlot

OBJECTIVE: Final = 0.3
SAMPLES: Final = 40
OWN: Final = 2_000
OTHERS: Final = 3_000
# Встречи, их прогоны, записи и находки — одним запросом на таблицу, как их оставил бы конвейер.
SEED: Final = """
WITH people AS (
    SELECT g, CASE WHEN g <= %(own)s THEN %(person)s::uuid ELSE md5('u' || (g %% 300))::uuid END
           AS owner,
           CASE WHEN g > %(own)s AND g %% 2 = 0 THEN %(org)s::uuid END AS org
    FROM generate_series(1, %(own)s + %(others)s) AS g
), meetings AS (
    INSERT INTO sessions (id, user_id, org_id, access, title, status, started_at, ended_at,
                          seconds, latest_run_id, notes_revision, line_count)
    SELECT md5('m' || g)::uuid, owner, org, CASE WHEN org IS NOT NULL THEN 'organization' END,
           'Встреча ' || g, 'completed', now() - g * interval '1 hour',
           now() - g * interval '1 hour' + interval '30 minutes', 1800, md5('r' || g)::uuid, 1, 0
    FROM people RETURNING id
), runs AS (
    INSERT INTO meeting_processing_runs (id, session_id, user_id, org_id, source,
                                         idempotency_key, state)
    SELECT md5('r' || g)::uuid, md5('m' || g)::uuid, owner, org, 'live', 'live', 'succeeded'
    FROM people
), notes AS (
    INSERT INTO meeting_notes (session_id, user_id, org_id, write_up, write_up_template,
                               write_up_run_id, findings_run_id, map)
    SELECT md5('m' || g)::uuid, owner, org,
           jsonb_build_object('version', 1, 'template_id', 'enhanced', 'sections',
               jsonb_build_array(jsonb_build_object('kind', 'summary', 'heading_code',
                   'summary', 'text', 'Обсудили план и решили, что делать дальше.'))),
           'enhanced', md5('r' || g)::uuid, md5('r' || g)::uuid,
           jsonb_build_object('label', 'Встреча', 'children', '[]'::jsonb)
    FROM people
), people_in AS (
    INSERT INTO meeting_participants (id, session_id, user_id, org_id, email, name, source)
    SELECT gen_random_uuid(), md5('m' || g)::uuid, owner, org, 'p' || n || '@example.com',
           'Участник ' || n, 'added'
    FROM people, generate_series(1, 3) AS n
)
INSERT INTO meeting_findings (id, session_id, user_id, org_id, run_id, revision, position, kind,
                              text, start_ms, end_ms)
SELECT gen_random_uuid(), md5('m' || g)::uuid, owner, org, md5('r' || g)::uuid, 1, n,
       (ARRAY['key_point', 'decision', 'action_item', 'risk'])[1 + n %% 4],
       'Находка ' || n, n * 1000, n * 1000 + 500
FROM people, generate_series(0, 7) AS n
"""


async def seed(connection: Connection, person: uuid.UUID) -> None:
    """The seeded home, its workspace written as the tables' owner."""
    org = uuid.uuid4()
    async with connection.transaction():
        await connection.execute(
            "INSERT INTO organizations (id, slug, name, created_by, state)"
            " VALUES (%s, %s, 'w', %s, 'active')",
            (org, f"w-{org.hex[:12]}", uuid.uuid4()),
        )
        await connection.execute(
            "INSERT INTO memberships (id, org_id, user_id, role, state)"
            " VALUES (%s, %s, md5('u0')::uuid, 'owner', 'active')",
            (uuid.uuid4(), org),
        )
        params = {"own": OWN, "others": OTHERS, "person": person, "org": org}
        await connection.execute(SEED, params)
        await connection.execute("ANALYZE sessions, meeting_findings, meeting_participants")


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


async def test_the_library_and_a_meeting_s_page_answer_within_the_objective(
    library_bench: LibraryBench, run_slot: RunSlot
) -> None:
    person = uuid.uuid4()
    connection = run_slot.claimed.connections[Home.EU]
    await seed(connection, person)
    deep = (await library_bench.get(person, "/v1/meetings", limit=100)).json()["next_cursor"]
    middle = await fetch_value(connection, "SELECT md5('m' || 1000)::uuid")
    http = library_bench.http

    first_page = await p95(lambda: http.get("/v1/meetings", headers=bearer(person)))
    deep_page = await p95(
        lambda: http.get("/v1/meetings", params={"cursor": deep}, headers=bearer(person))
    )
    page = await p95(lambda: http.get(f"/v1/meetings/{middle}", headers=bearer(person)))

    assert max(first_page, deep_page, page) <= OBJECTIVE, (first_page, deep_page, page)
