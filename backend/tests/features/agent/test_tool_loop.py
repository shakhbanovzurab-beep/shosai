"""Leo reads with tools: the rounds, the wrapper, the steps and what a run keeps (step 6)."""

import json
import uuid
from typing import Any

from shosai.core.ai.requests import ChatMessage, ChatRequest, Role
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.run_context import text_of
from shosai.features.agent.infrastructure.person_records import AgentFeedbackRecord
from tests.features.agent.tool_doubles import calling, saying
from tests.features.agent.turn_bench import HOME, TurnBench, stream_of
from tests.features.billing.people_bench import bearer
from tests.harness.connections import fetch_rows

QUESTION = "What did we decide on the budget?"


def unwrapped(message: ChatMessage) -> tuple[str, Any]:
    """A wrapped tool answer: its opening marker and the JSON between the markers."""
    lines = text_of(message).split("\n")
    return lines[0], json.loads("\n".join(lines[1:-1]))


async def run_rows(turn_bench: TurnBench, run_id: str) -> list[dict[str, Any]]:
    """The rows the run wrote after its question, in the thread's order."""
    rows = await fetch_rows(
        turn_bench.connection,
        "SELECT role, text, tool_calls, tool_name, digest, result_id, steps FROM agent_messages"
        " WHERE run_id = %s AND role <> 'user' ORDER BY created_at, id",
        (uuid.UUID(run_id),),
    )
    return [dict(row) for row in rows]


async def run_row(turn_bench: TurnBench, run_id: str) -> dict[str, Any]:
    """The run's numbers and its routing."""
    rows = await fetch_rows(
        turn_bench.connection,
        "SELECT rounds, tool_calls, routing FROM agent_runs WHERE id = %s",
        (uuid.UUID(run_id),),
    )
    return dict(rows[0])


async def test_leo_reads_with_a_tool_and_answers_from_what_it_returned(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    round_one = calling(("notes__search", '{"query": "budget"}'))
    turn_bench.model.scripts = [[saying("Let me look.")[0], *round_one], saying("Travel was cut.")]

    events = stream_of(await turn_bench.ask(person, thread, QUESTION))
    first, second = turn_bench.model.calls
    marker, result = unwrapped(second.messages[-1])
    run_id = events[0][2]["run_id"]
    rows = await run_rows(turn_bench, run_id)
    history = await turn_bench.http.get(
        f"/v1/agent/threads/{thread}/messages", headers=bearer((HOME, person))
    )
    answer = history.json()["items"][0]
    spans = {span.name: span for span in turn_bench.observed[1].get_finished_spans()}

    assert [kind for kind, _, _ in events] == [
        "run.started", "text.delta", "step.started", "step.completed", "text.delta",
        "run.completed",
    ]  # fmt: skip
    assert events[2][2] == {
        "id": "step-1",
        "seq": 1,
        "activity": "notes.search",
        "detail": "budget",
    }
    assert "".join(data["text"] for kind, _, data in events if kind == "text.delta") == (
        "Let me look.\n\nTravel was cut."
    )
    assert {tool.name for tool in first.tools} == {
        "core__read_result", "core__load_toolset", "core__navigate", "notes__search",
        "notes__wait", "notes__fail", "tasks__search", "tasks__create", "files__search",
    }  # fmt: skip
    assert second.messages[-2].tool_calls[0].name == "notes__search"
    assert marker.startswith("<<untrusted source=meeting:speech id=")
    assert result == {"items": ["Budget review: travel cut by 20%"]}
    assert [row["role"] for row in rows] == ["assistant", "tool", "assistant"]
    assert rows[0]["text"] == "Let me look."
    assert rows[0]["tool_calls"][0]["name"] == "notes__search"
    assert rows[1]["tool_name"] == "notes.search"
    assert rows[1]["digest"]["text"].startswith("<<untrusted source=meeting:speech")
    assert rows[2]["text"] == "Let me look.\n\nTravel was cut."
    assert await run_row(turn_bench, run_id) == {
        "rounds": 2, "tool_calls": 1,
        "routing": {"rule": "rules_v2", "selected": ["core", "notes", "tasks", "files"],
                    "reading": [], "deferred": ["archive"], "loaded": [], "used": ["notes"],
                    "wrote": [], "routed": [], "asked": False},
    }  # fmt: skip
    traced = dict(spans["tool.notes.search"].attributes or {})
    assert (traced["tool.effect"], traced["tool.outcome"]) == ("read", "ok")
    assert int(str(traced["tool.result_tokens"])) > 0
    assert [item["role"] for item in history.json()["items"]] == ["assistant", "user"]
    assert answer["steps"] == [
        {"id": "step-1", "activity": "notes.search", "detail": "budget", "status": "done",
         "duration_ms": answer["steps"][0]["duration_ms"]}
    ]  # fmt: skip


def reading_the_ref(request: ChatRequest) -> list[Any]:
    """The model reads the whole result the digest named."""
    _, digest = unwrapped(request.messages[-1])
    return calling(("core__read_result", json.dumps({"result_ref": digest["result_ref"]})))


async def test_a_result_over_its_budget_is_a_digest_and_read_whole_by_its_ref(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.tools.items = [f"Встреча {n}: бюджет, поездки, решения" for n in range(40)]
    turn_bench.model.scripts = [
        calling(("notes__search", '{"query": "budget"}')),
        reading_the_ref,
        saying("Forty meetings."),
    ]

    events = stream_of(await turn_bench.ask(person, thread, QUESTION))
    _, digest = unwrapped(turn_bench.model.calls[1].messages[-1])
    marker, page = unwrapped(turn_bench.model.calls[2].messages[-1])
    kept = await fetch_rows(
        turn_bench.connection,
        "SELECT tool_name, spaces, payload FROM agent_tool_results WHERE id = %s",
        (uuid.UUID(digest["result_ref"]),),
    )

    assert digest["truncated"] is True
    assert digest["omitted"] == {"items": 40}
    assert 0 < len(digest["result"]["items"]) < 40
    assert "core__read_result" in digest["note"]
    assert (kept[0]["tool_name"], kept[0]["spaces"]) == ("notes.search", [])
    assert marker.startswith("<<untrusted source=meeting:speech id=")
    assert page["tool"] == "notes.search"
    assert page["next_cursor"] is None
    assert json.loads(page["text"]) == {"items": turn_bench.tools.items}
    assert [data["activity"] for kind, _, data in events if kind == "step.completed"] == [
        "notes.search",
        "core.read_result",
    ]


async def test_later_turns_read_the_answers_not_the_rounds_and_regenerate_replaces_both(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    searching = calling(("notes__search", '{"query": "budget"}'))
    turn_bench.model.scripts = [searching, saying("Cut.")]
    await turn_bench.ask(person, thread, QUESTION)
    turn_bench.model.calls.clear()
    turn_bench.model.scripts = [saying("Yes.")]
    await turn_bench.ask(person, thread, "Are you sure?")
    follow_up = turn_bench.model.calls[0]
    turn_bench.model.scripts = [searching, saying("Travel.")]
    last = stream_of(await turn_bench.ask(person, thread, "And travel?"))
    turn_bench.model.scripts = [saying("Travel, again.")]
    reply = uuid.UUID(last[0][2]["reply_id"])
    async with turn_bench.homes.transactions.begin(TenancyScope(HOME, person)) as session:
        session.add(
            AgentFeedbackRecord(
                message_id=reply, user_id=person, thread_id=uuid.UUID(thread), rating="useful"
            )
        )

    await turn_bench.ask(person, thread, "And travel?", regenerate_of=last[0][2]["message_id"])
    replaced = await run_rows(turn_bench, last[0][2]["run_id"])
    rated = await fetch_rows(
        turn_bench.connection, "SELECT 1 FROM agent_feedback WHERE message_id = %s", (reply,)
    )

    assert [message.role for message in follow_up.messages] == [
        Role.SYSTEM, Role.USER, Role.ASSISTANT, Role.USER,
    ]  # fmt: skip
    assert text_of(follow_up.messages[2]) == "Cut."
    assert replaced == []
    # Оценка уходит вместе с заменённым ответом.
    assert rated == []
