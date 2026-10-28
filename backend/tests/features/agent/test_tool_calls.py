"""Calls that do not run, calls that fail, the cabinet's action and the rounds' end (step 6)."""

import json
import uuid
from typing import Any

from shosai.core.ai.requests import ChatRequest, Role
from shosai.core.ai.results import ChatDelta
from shosai.features.agent.application.run_context import text_of
from shosai.features.agent.infrastructure.prompts import CONCLUDE, LAST_ROUND
from tests.features.agent.tool_doubles import calling, saying
from tests.features.agent.turn_bench import TurnBench, stream_of
from tests.features.agent.turn_doubles import Script
from tests.harness.connections import fetch_rows

SEARCH = ("notes__search", '{"query": "budget"}')


def answers(request: ChatRequest) -> list[Any]:
    """What the model read back for each call of its last round, unwrapped."""
    read = []
    for message in request.messages:
        if message.role is Role.TOOL:
            text = text_of(message)
            if text.startswith("<<untrusted"):
                text = "\n".join(text.split("\n")[1:-1])
            read.append(json.loads(text))
    return read


def codes(request: ChatRequest) -> list[str | None]:
    """The error code of each answer, None for a result."""
    return [answer.get("error", {}).get("code") for answer in answers(request)]


async def asked(turn_bench: TurnBench, *rounds: list[ChatDelta]) -> list[Any]:
    """A turn whose model plays the rounds, then answers: its stream."""
    turn_bench.model.scripts = [*rounds, saying("Done.")]
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    return stream_of(await turn_bench.ask(person, thread, "Look it up."))


async def test_a_call_that_cannot_run_is_answered_with_an_error_and_never_runs(
    turn_bench: TurnBench,
) -> None:
    events = await asked(
        turn_bench,
        calling(
            ("mail__send", "{}"),
            ("notes__search", '{"q": 1}'),
            ("core__load_toolset", '{"name": "mail"}'),
            ("tasks__delete", '{"query": "x"}'),
            SEARCH,
        ),
    )
    read = answers(turn_bench.model.calls[1])

    assert codes(turn_bench.model.calls[1]) == [
        "unknown_tool", "invalid_arguments", "invalid_arguments", "unknown_tool", None,
    ]  # fmt: skip
    assert set(read[1]["error"]["fields"].split(", ")) == {"q", "query"}
    assert read[2]["error"]["fields"] == "name"
    assert turn_bench.tools.ran == ["budget"]
    assert [data["activity"] for kind, _, data in events if kind == "step.started"] == [
        "notes.search"
    ]
    assert events[-1][0] == "run.completed"


async def test_a_round_runs_eight_calls_and_refuses_the_cut_one(turn_bench: TurnBench) -> None:
    nine = calling(*[("notes__search", json.dumps({"query": f"q{n}"})) for n in range(9)])
    cut = calling(SEARCH, ("notes__search", '{"query": "bud'), finish="length")

    await asked(turn_bench, nine, cut)

    assert codes(turn_bench.model.calls[1]) == [None] * 8 + ["too_many_calls"]
    assert codes(turn_bench.model.calls[2])[9:] == [None, "cut_call"]
    assert sorted(turn_bench.tools.ran) == sorted([f"q{n}" for n in range(8)] + ["budget"])


async def test_a_slow_or_broken_tool_is_an_error_the_model_explains(
    turn_bench: TurnBench,
) -> None:
    events = await asked(
        turn_bench, calling(("notes__wait", '{"query": "a"}'), ("notes__fail", '{"query": "b"}'))
    )
    failed = {data["activity"]: data for kind, _, data in events if kind == "step.failed"}

    assert codes(turn_bench.model.calls[1]) == ["timeout", "failed"]
    assert failed["notes.wait"]["code"] == "timeout"
    assert failed["notes.fail"]["code"] == "failed"
    assert {"id", "seq", "activity", "duration_ms", "code"} <= set(failed["notes.fail"])
    assert events[-1][0] == "run.completed"


async def test_navigate_sends_the_cabinet_a_page_and_refuses_anything_else(
    turn_bench: TurnBench,
) -> None:
    events = await asked(
        turn_bench,
        calling(("core__navigate", '{"to": "/app/kanban?view=board"}')),
        calling(("core__navigate", '{"to": "https://example.com/app"}')),
        # Страницы бэклога нет: модель её выдумала (отчёт владельца 2026-10-28).
        calling(("core__navigate", '{"to": "/app/tasks"}')),
    )
    refused = json.loads(text_of(turn_bench.model.calls[3].messages[-1]))

    assert [data for kind, _, data in events if kind == "client.action"] == [
        {"navigate": {"to": "/app/kanban"}}
    ]
    assert codes(turn_bench.model.calls[3]) == [None, "invalid_arguments", "not_found"]
    assert "/app/kanban (Kanban boards with all of the user's tasks)" in refused["error"]["pages"]


async def test_the_model_is_asked_to_conclude_after_four_rounds_and_the_tenth_has_no_tools(
    turn_bench: TurnBench,
) -> None:
    rounds: list[Script] = [calling(SEARCH) for _ in range(9)]
    turn_bench.model.scripts = [*rounds, [ChatDelta(text="Enough."), *calling(SEARCH)]]
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)

    events = stream_of(await turn_bench.ask(person, thread, "Look it up."))
    calls = turn_bench.model.calls
    run = await fetch_rows(
        turn_bench.connection,
        "SELECT rounds, tool_calls FROM agent_runs WHERE id = %s",
        (uuid.UUID(events[0][2]["run_id"]),),
    )

    assert len(calls) == 10
    assert [text_of(call.messages[-1]) == CONCLUDE for call in calls[:9]] == [False] * 4 + [
        True
    ] * 5
    assert (text_of(calls[9].messages[-1]), calls[9].tools) == (LAST_ROUND, ())
    assert all(call.tools for call in calls[:9])
    assert (run[0]["rounds"], run[0]["tool_calls"]) == (10, 9)
    assert (events[-1][0], events[-1][2]["outcome"]) == ("run.completed", "answered")
