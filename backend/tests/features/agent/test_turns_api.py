"""A turn from admission to its one end, over the API (agent step 5a); a turn the person asked
to think longer reasons at its model's highest effort."""

import asyncio
import uuid

from shosai.core.ai.requests import ReasoningEffort
from shosai.features.agent.domain.runs import ENDED_LOG
from shosai.features.agent.infrastructure.run_keys import log_key
from tests.features.agent.turn_bench import TurnBench, stream_of
from tests.harness.connections import fetch_rows, fetch_value


async def started_run(bench: TurnBench, thread: str) -> str:
    """The run a background turn on the thread started, once its log has it."""
    for _ in range(300):
        for sent in bench.queue.sent:
            if str(sent.thread_id) == thread:
                return str(sent.run_id)
        await asyncio.sleep(0.01)
    raise AssertionError("ход не начался")


async def test_a_turn_streams_its_answer_and_keeps_it(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)

    answer = await turn_bench.ask(person, thread, "  What is Shosai?  ")
    events = stream_of(answer)

    assert answer.status_code == 200
    assert answer.headers["content-type"].startswith("text/event-stream")
    assert events[0][0] == "run.started"
    assert [seq for _, seq, _ in events] == list(range(1, len(events) + 1))
    assert "".join(data["text"] for kind, _, data in events if kind == "text.delta") == (
        "Hello, world."
    )
    started, ended = events[0][2], events[-1]
    assert ended[0] == "run.completed"
    assert ended[2] == {
        "message_id": started["reply_id"],
        "outcome": "answered",
        "truncated": False,
    }
    history = await turn_bench.http.get(
        f"/v1/agent/threads/{thread}/messages",
        headers={"Authorization": answer.request.headers["Authorization"]},
    )
    assert [(m["role"], m["text"], m["status"]) for m in history.json()["items"]] == [
        ("assistant", "Hello, world.", "done"),
        ("user", "What is Shosai?", None),
    ]
    run = await fetch_rows(
        turn_bench.connection,
        "SELECT status, outcome_code, input_tokens, output_tokens, ended_at IS NOT NULL AS ended"
        " FROM agent_runs WHERE id = %s",
        (uuid.UUID(started["run_id"]),),
    )
    assert [dict(row) for row in run] == [
        {"status": "completed", "outcome_code": "answered", "input_tokens": 12,
         "output_tokens": 3, "ended": True}
    ]  # fmt: skip
    title = await fetch_value(
        turn_bench.connection,
        "SELECT title FROM agent_threads WHERE id = %s",
        (uuid.UUID(thread),),
    )
    assert title == "What is Shosai?"
    # Законченный прогон держит журнал минуты для переподключения, а не час.
    kept_ms = await turn_bench.valkey.pttl(log_key(uuid.UUID(started["run_id"])))
    assert 0 < kept_ms <= ENDED_LOG.total_seconds() * 1000


async def test_the_same_key_streams_the_same_run_once(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)

    first = stream_of(await turn_bench.ask(person, thread, key="question-1"))
    again = stream_of(await turn_bench.ask(person, thread, key="question-1"))
    reused = await turn_bench.ask(person, thread, "Another question", key="question-1")

    assert again == first
    assert len(turn_bench.queue.sent) == 1
    assert reused.json()["error"]["code"] == "idempotency_key_reused"


async def test_a_busy_thread_is_refused_unless_the_turn_supersedes(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.held_calls = 1
    turn_bench.model.gate.clear()
    first = asyncio.create_task(turn_bench.ask(person, thread, "First"))
    await started_run(turn_bench, thread)

    busy = await turn_bench.ask(person, thread, "Second")
    superseding = await turn_bench.ask(person, thread, "Third", supersede=True)
    stopped = stream_of(await first)

    assert (busy.status_code, busy.json()["error"]["code"]) == (409, "thread_busy")
    assert stopped[-1][0] == "run.completed"
    assert stopped[-1][2]["outcome"] == "stopped"
    assert stream_of(superseding)[-1][2]["outcome"] == "answered"


async def test_stop_keeps_the_text_written_so_far(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.held_calls = 1
    turn_bench.model.gate.clear()
    asked = asyncio.create_task(turn_bench.ask(person, thread))
    run_id = await started_run(turn_bench, thread)
    await asyncio.sleep(0.3)

    headers = {"Authorization": f"Bearer person:{person}:eu"}
    stop = await turn_bench.http.post(f"/v1/agent/runs/{run_id}/cancel", headers=headers)
    again = await turn_bench.http.post(f"/v1/agent/runs/{run_id}/cancel", headers=headers)
    events = stream_of(await asked)

    assert (stop.status_code, again.status_code) == (202, 202)
    assert events[-1][0] == "run.completed"
    assert events[-1][2]["outcome"] == "stopped"
    kept = await fetch_rows(
        turn_bench.connection,
        "SELECT status, text FROM agent_messages WHERE run_id = %s AND role = 'assistant'",
        (uuid.UUID(run_id),),
    )
    assert [tuple(row.values()) for row in kept] == [("stopped", "Hello")]


async def test_a_turn_asked_to_think_longer_reasons_at_the_highest_effort(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)

    await turn_bench.ask(person, thread, "Plan my week.", think_longer=True)
    await turn_bench.ask(person, thread, "Thanks!")

    assert [call.reasoning for call in turn_bench.model.calls] == [ReasoningEffort.HIGH, None]
