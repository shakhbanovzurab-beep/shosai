"""Refusals before the stream, failures, lost workers and resumes (agent step 5a)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.kernel.homes import Home
from shosai.features.agent.application.lost_runs import LostRuns
from shosai.features.agent.infrastructure.run_keys import FLEET_WORKERS, lease_key, log_key
from shosai.features.billing.contracts import TokenRoute
from tests.features.agent.test_turns_api import started_run
from tests.features.agent.turn_bench import TurnBench, stream_of
from tests.harness.connections import fetch_rows


def auth(person: uuid.UUID, home: Home = Home.EU) -> dict[str, str]:
    """The test's bearer of the person."""
    return {"Authorization": f"Bearer person:{person}:{home.value}"}


async def test_refusals_come_before_the_stream(turn_bench: TurnBench) -> None:
    person, russian = uuid.uuid4(), uuid.uuid4()
    thread = await turn_bench.thread(person)
    theirs = await turn_bench.thread(russian, Home.RU)

    empty = await turn_bench.ask(person, thread, "   ")
    stranger = await turn_bench.ask(uuid.uuid4(), thread)
    unconsented = await turn_bench.ask(russian, theirs, home=Home.RU)
    turn_bench.terms.route = TokenRoute.STOP
    spent = await turn_bench.ask(person, thread)
    turn_bench.terms.route = TokenRoute.WITHIN_ALLOWANCE
    await turn_bench.valkey.delete(FLEET_WORKERS)
    full = await turn_bench.ask(person, thread)

    assert [(a.status_code, a.json()["error"]["code"]) for a in (empty, stranger)] == [
        (422, "question_invalid"),
        (404, "thread_not_found"),
    ]
    assert (unconsented.status_code, unconsented.json()["error"]["code"]) == (
        403,
        "consent_required",
    )
    assert (spent.status_code, spent.json()["error"]["params"]) == (
        402,
        {"limit": "standard_daily_tokens"},
    )
    assert (full.status_code, full.json()["error"]["code"]) == (429, "agent_busy")
    assert full.headers["Retry-After"] == "5"
    assert turn_bench.queue.sent == []


async def test_a_person_has_at_most_two_runs_at_once(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    threads = [await turn_bench.thread(person) for _ in range(3)]
    turn_bench.queue.hold = True
    running = [asyncio.create_task(turn_bench.ask(person, thread)) for thread in threads[:2]]
    for thread in threads[:2]:
        await started_run(turn_bench, thread)

    third = await turn_bench.ask(person, threads[2])

    assert (third.status_code, third.json()["error"]["code"]) == (429, "too_many_runs")
    for task in running:
        task.cancel()
    await asyncio.gather(*running, return_exceptions=True)


async def test_a_failing_model_fails_the_run_once_and_keeps_its_text(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.failure = AiCallError(AiFailure.PROVIDER_ERROR)

    events = stream_of(await turn_bench.ask(person, thread))

    assert [kind for kind, _, _ in events].count("run.failed") == 1
    assert events[-1][0:3:2] == ("run.failed", {"code": "model_unavailable"})
    assert "run.completed" not in {kind for kind, _, _ in events}
    kept = await fetch_rows(
        turn_bench.connection,
        "SELECT status, text FROM agent_messages WHERE thread_id = %s AND role = 'assistant'",
        (uuid.UUID(thread),),
    )
    assert [tuple(row.values()) for row in kept] == [("failed", "Hello, world.")]


async def test_a_lost_worker_s_run_is_swept_once(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.queue.hold = True
    asked = asyncio.create_task(turn_bench.ask(person, thread))
    run_id = await started_run(turn_bench, thread)
    await turn_bench.valkey.delete(lease_key(uuid.UUID(thread)))
    later = datetime.now(UTC) + timedelta(seconds=31)
    parts = turn_bench.parts

    async with turn_bench.sweeping() as transactions:
        swept = LostRuns(
            transactions,
            (parts.run_log, parts.leases, parts.fleet),
            parts.telemetry.metrics,
            lambda: later,
        )
        first, again = await swept.sweep(Home.EU), await swept.sweep(Home.EU)
    events = stream_of(await asked)

    assert (first, again) == (1, 0)
    assert events[-1][0:3:2] == ("run.failed", {"code": "process_lost"})
    row = await fetch_rows(
        turn_bench.connection,
        "SELECT status, outcome_code FROM agent_runs WHERE id = %s",
        (uuid.UUID(run_id),),
    )
    assert [tuple(r.values()) for r in row] == [("failed", "process_lost")]


async def test_a_stream_resumes_after_the_last_event_seen(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    events = stream_of(await turn_bench.ask(person, thread))
    run_id = events[0][2]["run_id"]
    path = f"/v1/agent/runs/{run_id}/events"

    rest = await turn_bench.http.get(path, headers=auth(person) | {"Last-Event-ID": "1"})
    foreign = await turn_bench.http.get(path, headers=auth(uuid.uuid4()))
    await turn_bench.valkey.delete(log_key(uuid.UUID(run_id)))
    gone = await turn_bench.http.get(path, headers=auth(person))

    assert stream_of(rest) == events[1:]
    assert (foreign.status_code, foreign.json()["error"]["code"]) == (404, "run_not_found")
    assert (gone.status_code, gone.json()["error"]["code"]) == (410, "run_events_gone")


async def test_a_silent_log_ends_with_the_end_the_run_recorded(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.queue.hold = True
    asked = asyncio.create_task(turn_bench.ask(person, thread))
    run_id = await started_run(turn_bench, thread)

    await turn_bench.connection.execute(
        "UPDATE agent_runs SET status = 'completed', outcome_code = 'stopped', ended_at = now()"
        " WHERE id = %s",
        (uuid.UUID(run_id),),
    )
    events = stream_of(await asked)

    assert [kind for kind, _, _ in events] == ["run.started", "run.completed"]
    assert events[-1][1:] == (2, {"message_id": None, "outcome": "stopped", "truncated": False})
