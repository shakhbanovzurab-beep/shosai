"""A call that sends data outside Shosai (Leo §7.4; agent step 13b): at once while the run has
read only the person's own data, as a card once it has read text from outside; approved, it
runs once and the epilogue reads its result as the call's own answer; rejected, it never runs;
behind its switch, it is never offered."""

import uuid
from typing import Final

import pytest

from shosai.core.agent_tools.sources import SourceKind, SourceRef
from shosai.core.ai.requests import ChatMessage, Role
from shosai.features.agent.application.run_context import text_of
from tests.features.agent.action_bench import ActionBench
from tests.features.agent.tool_doubles import ProbeTools, calling, saying
from tests.features.agent.turn_bench import HOME, TurnBench, stream_of
from tests.features.billing.people_bench import bearer

READ: Final = ("notes__search", '{"query": "budget"}')
SEARCH: Final = ("web__lookup", '{"query": "launch date"}')
PAGE: Final = SourceRef(SourceKind.WEB, "https://news.example/launch", "Launch moved")
TOOL_ROWS: Final = (
    "SELECT digest FROM agent_messages WHERE run_id = %s AND role = 'tool' ORDER BY created_at"
)


@pytest.fixture
def probe_tools() -> ProbeTools:
    """The probe's tools with its egress search."""
    return ProbeTools(pages=[PAGE])


def tool_answers(messages: tuple[ChatMessage, ...]) -> list[str]:
    """What the model read for each call."""
    return [text_of(message) for message in messages if message.role is Role.TOOL]


async def test_a_run_that_read_only_the_person_s_data_searches_at_once(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [calling(READ, SEARCH), saying("In May [1].")]

    events = stream_of(await turn_bench.ask(person, thread, "When is the launch?"))

    assert turn_bench.tools.ran == ["budget", "web:launch date"]
    assert not [kind for kind, _, _ in events if kind == "action.proposed"]
    [*_, sources] = [data for kind, _, data in events if kind == "sources"]
    assert [(s["kind"], s["id"], s["space"]) for s in sources["sources"]] == [
        ("web", "https://news.example/launch", "news.example")
    ]
    answers = tool_answers(turn_bench.model.calls[1].messages)
    assert answers[1].startswith("<<untrusted source=web ")


async def test_a_tainted_run_asks_first_and_the_epilogue_reads_the_result(
    action_bench: ActionBench,
) -> None:
    turns, person = action_bench.turns, uuid.uuid4()
    thread = await turns.thread(person)
    turns.model.scripts = [calling(READ), calling(SEARCH), saying("It moved to May [1].")]

    events = stream_of(await turns.ask(person, thread, "Find the launch date."))
    card = next(data["action"] for kind, _, data in events if kind == "action.proposed")
    ran_before = list(turns.tools.ran)
    approved = await action_bench.decide(person, card, "approve")
    await action_bench.queue.settle()
    tail = stream_of(
        await turns.http.get(
            f"/v1/agent/runs/{events[0][2]['run_id']}/events",
            headers=bearer((HOME, person)) | {"Last-Event-ID": str(events[-1][1])},
        )
    )
    epilogue = turns.model.calls[-1].messages
    rows = await action_bench.rows(TOOL_ROWS, uuid.UUID(events[0][2]["run_id"]))

    assert ran_before == ["budget"]
    assert (card["tool"], card["warning"], card["taint"], card["reversibility"]) == (
        "web.lookup", True, "meeting:speech", "irreversible",
    )  # fmt: skip
    assert card["preview"]["fields"] == [{"label": "Query", "value": "launch date"}]
    assert approved.json()["status"] == "succeeded"
    assert turns.tools.ran == ["budget", "web:launch date"]
    searched = tool_answers(epilogue)[-1]
    assert searched.startswith("<<untrusted source=web ")
    assert "https://news.example/launch" in searched
    assert text_of(epilogue[-1]).endswith(
        "the web.lookup call you asked the person to approve was approved and done. "
        "Its result is now that call's answer."
    )
    assert "untrusted source=web" in rows[-1]["digest"]["text"]
    kinds = [kind for kind, _, _ in tail]
    assert kinds[-3:] == ["sources", "text.delta", "run.completed"]


async def test_a_rejected_search_never_runs(action_bench: ActionBench) -> None:
    turns, person = action_bench.turns, uuid.uuid4()
    thread = await turns.thread(person)
    turns.model.scripts = [calling(READ), calling(SEARCH)]
    events = stream_of(await turns.ask(person, thread, "Find the launch date."))
    card = next(data["action"] for kind, _, data in events if kind == "action.proposed")

    rejected = await action_bench.decide(person, card, "reject")
    await action_bench.queue.settle()

    assert rejected.json()["status"] == "rejected"
    assert turns.tools.ran == ["budget"]


async def test_one_card_waits_at_a_time(action_bench: ActionBench) -> None:
    turns, person = action_bench.turns, uuid.uuid4()
    thread = await turns.thread(person)
    write = ("tasks__create", '{"query": "Call Anna"}')
    turns.model.scripts = [calling(READ), calling(SEARCH, write)]

    events = stream_of(await turns.ask(person, thread, "Search, then make a task."))

    cards = [data["action"]["tool"] for kind, _, data in events if kind == "action.proposed"]
    rows = await action_bench.rows(TOOL_ROWS, uuid.UUID(events[0][2]["run_id"]))
    assert cards == ["web.lookup"]
    assert '"code":"one_change"' in rows[-1]["digest"]["text"]
    assert turns.tools.executed == []


async def test_a_person_who_switched_web_search_off_is_never_offered_it(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    await turn_bench.connection.execute(
        "INSERT INTO agent_settings (user_id, web_search) VALUES (%s, false)", (person,)
    )
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [calling(SEARCH), saying("I cannot search.")]

    await turn_bench.ask(person, thread, "When is the launch?")

    offered = [tool.name for tool in turn_bench.model.calls[0].tools]
    assert "web__lookup" not in offered
    assert turn_bench.tools.ran == []
