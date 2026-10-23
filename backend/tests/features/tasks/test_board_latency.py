"""A full board answers within §16.3 and four round trips, and a board and a person keep
their limits (step 4).

The board holds 1 000 open cards and 200 done ones across its columns, half of the open
cards with a checklist, every open card with a running stopwatch after two closed spans and
every fifth with a timer (§3.9), among tasks of others; the process's startup heap is frozen as the
running process freezes it (ADR 0065). Its read sets the
board right and answers its cards with their counts: p95 at most 300 ms. A full board takes
no more open cards but takes done ones; a person holds 50 boards.
"""

import gc
import statistics
import time
import uuid
from typing import Final

from sqlalchemy import event
from sqlalchemy.engine import Engine

from shosai.core.kernel.homes import Home
from shosai.core.runtime.heap import freeze_startup_heap
from tests.features.tasks.board_helpers import board, code_of, column_ids, made
from tests.features.tasks.task_bench import TaskBench, bearer
from tests.harness.connections import Connection
from tests.harness.run_slot import RunSlot

OBJECTIVE: Final = 0.3
SAMPLES: Final = 30
SEED: Final = """
INSERT INTO tasks (id, user_id, title, status, completed_at, created_at, updated_at)
SELECT md5(%(board)s || 't' || g)::uuid, %(person)s::uuid, 'Карточка ' || g,
       CASE WHEN g > 1000 THEN 'done' WHEN g %% 3 = 0 THEN 'in_progress' ELSE 'todo' END,
       CASE WHEN g > 1000 THEN now() - (g %% 20) * interval '1 day' END, now(), now()
FROM generate_series(1, 1200) AS g;
INSERT INTO task_placements (user_id, task_id, board_id, column_id, rank)
SELECT %(person)s::uuid, md5(%(board)s || 't' || g)::uuid, %(board)s::uuid,
       CASE WHEN g > 1000 THEN %(done)s::uuid WHEN g %% 3 = 0 THEN %(doing)s::uuid
            ELSE %(todo)s::uuid END,
       lpad(g::text, 5, '0') || 'V'
FROM generate_series(1, 1200) AS g;
INSERT INTO task_subtasks (id, task_id, user_id, title, done, rank)
SELECT gen_random_uuid(), md5(%(board)s || 't' || g)::uuid, %(person)s::uuid, 'Пункт',
       g %% 4 = 0, 'V'
FROM generate_series(1, 1000, 2) AS g;
INSERT INTO task_clock_spans (id, task_id, user_id, column_id, started_at, stopped_at)
SELECT gen_random_uuid(), md5(%(board)s || 't' || g)::uuid, %(person)s::uuid,
       CASE WHEN s = 1 THEN %(todo)s::uuid ELSE %(doing)s::uuid END,
       now() - (4 - s) * interval '1 hour',
       CASE WHEN s < 3 THEN now() - (3 - s) * interval '1 hour' - interval '10 minutes' END
FROM generate_series(1, 1000) AS g, generate_series(1, 3) AS s;
UPDATE tasks SET stopwatch_since = now() - interval '1 hour', stopwatch_total_ms = 6000000,
       stopwatch_by_column = jsonb_build_object(%(todo)s::text, 3000000, %(doing)s::text, 3000000)
WHERE id IN (SELECT md5(%(board)s || 't' || g)::uuid FROM generate_series(1, 1000) AS g);
UPDATE tasks SET timer_length_ms = 3600000, timer_ends_at = now() + interval '30 minutes'
WHERE id IN (SELECT md5(%(board)s || 't' || g)::uuid FROM generate_series(5, 1000, 5) AS g);
INSERT INTO tasks (id, user_id, title, created_at, updated_at)
SELECT gen_random_uuid(), md5('other' || (g %% 300))::uuid, 'Чужая', now(), now()
FROM generate_series(1, 5000) AS g;
ANALYZE tasks, task_placements, task_subtasks, task_clock_spans
"""


async def seed(connection: Connection, person: uuid.UUID, board: tuple[str, str, str, str]) -> None:
    """The full board of the person, written as the workers' bulk loads write."""
    board_id, todo, doing, done = board
    params = {"person": person, "board": board_id, "todo": todo, "doing": doing, "done": done}
    async with connection.transaction():
        for statement in SEED.split(";"):
            await connection.execute(statement, params)


async def test_a_board_of_a_thousand_open_cards_answers_within_the_objective(
    task_bench: TaskBench, run_slot: RunSlot
) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    todo, doing, done = column_ids(await board(task_bench, me, board_id))
    await seed(run_slot.claimed.connections[Home.EU], me, (board_id, todo, doing, done))
    headers = bearer(me)
    path = f"/v1/boards/{board_id}"
    for _ in range(3):
        assert (await task_bench.http.get(path, headers=headers)).status_code == 200
    took: list[float] = []
    # Как рабочий процесс после старта (ADR 0065): сборщик не обходит уже живущую кучу.
    freeze_startup_heap()
    try:
        for _ in range(SAMPLES):
            started = time.perf_counter()
            answer = await task_bench.http.get(path, headers=headers)
            took.append(time.perf_counter() - started)
            assert answer.status_code == 200
    finally:
        gc.unfreeze()
    read = await task_bench.http.get(path, headers=headers)
    cards = [card for column in read.json()["columns"] for card in column["cards"]]
    full = await task_bench.call(
        me, "POST", f"{path}/cards", {"title": "Ещё", "column_id": todo, "position": 0}
    )
    finished = await task_bench.call(
        me, "POST", f"{path}/cards", {"title": "Сделано", "column_id": done, "position": 0}
    )

    assert len(cards) == 1200
    assert sum(card["stopwatch"] is not None for card in cards) == 1000
    assert sum(card["timer"] is not None for card in cards) == 200
    p95 = statistics.quantiles(took, n=20)[-1]
    assert p95 <= OBJECTIVE, (
        f"p95 {p95 * 1000:.0f} ms, median {statistics.median(took) * 1000:.0f} ms"
    )
    assert (full.status_code, code_of(full)) == (409, "board_full")
    assert finished.status_code == 201


async def test_a_person_holds_fifty_boards(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    for _ in range(50):
        await made(task_bench, me)

    refused = await task_bench.call(
        me, "POST", "/v1/boards", {"name": "Ещё", "icon": "book", "template": "simple"}
    )

    assert (refused.status_code, code_of(refused)) == (409, "boards_full")


async def test_a_board_read_stays_within_four_round_trips(task_bench: TaskBench) -> None:
    me = uuid.uuid4()
    board_id = await made(task_bench, me)
    todo = column_ids(await board(task_bench, me, board_id))[0]
    await task_bench.call(
        me, "POST", f"/v1/boards/{board_id}/cards", {"title": "А", "column_id": todo, "position": 0}
    )
    statements: list[str] = []

    def counted(*args: object) -> None:
        statements.append(str(args[2]))

    event.listen(Engine, "before_cursor_execute", counted)
    try:
        await task_bench.call(me, "GET", f"/v1/boards/{board_id}")
    finally:
        event.remove(Engine, "before_cursor_execute", counted)

    # Настройки транзакции, доска с выбором входящих, колонки, карточки со счётчиками.
    assert len(statements) <= 4, statements
