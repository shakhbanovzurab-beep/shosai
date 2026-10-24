"""An answer's sources: numbered by the tools, named with their spaces (step 6, AG-D1)."""

import json
import uuid
from typing import Any, cast

from shosai.core.agent_tools.sources import SourceKind, SourceRef
from shosai.core.ai.requests import ChatMessage
from shosai.core.i18n.locales import LOCALES
from shosai.features.agent.application.run_context import text_of
from shosai.features.agent.domain.spaces import PERSONAL_SPACE, personal_space
from shosai.features.notes.infrastructure.meeting_records import MEETING_RESOURCE
from tests.features.agent.test_tool_loop import unwrapped
from tests.features.agent.tool_doubles import calling, saying
from tests.features.agent.turn_bench import HOME, TurnBench, stream_of
from tests.features.billing.people_bench import bearer
from tests.harness.connections import fetch_rows
from tests.support.access_model import MemberRow, WorkspaceRow, World
from tests.support.isolation import write_world


async def a_workspace_of(turn_bench: TurnBench, person: uuid.UUID) -> uuid.UUID:
    """An active workspace, named `w`, with an owner and the person as its member."""
    org = uuid.uuid4()
    world = World(
        workspaces=[WorkspaceRow(org, "active")],
        members=[
            MemberRow(uuid.uuid4(), org, uuid.uuid4(), "owner", "active"),
            MemberRow(uuid.uuid4(), org, person, "member", "active"),
        ],
    )
    await write_world(turn_bench.connection, MEETING_RESOURCE, world)
    return org


def read_back(message: ChatMessage) -> dict[str, Any]:
    """What the model read for a call: the JSON inside the wrapper, or the JSON itself."""
    text = text_of(message)
    found = unwrapped(message)[1] if text.startswith("<<untrusted") else json.loads(text)
    return cast("dict[str, Any]", found)


def listed(source: dict[str, Any]) -> dict[str, Any]:
    """A source as the cabinet reads it."""
    return {key: source[key] for key in ("id", "kind", "title", "space", "locator", "quote")}


async def test_an_answer_cites_the_sources_its_tools_named_in_their_spaces(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    org = await a_workspace_of(turn_bench, person)
    turn_bench.tools.sources = [
        SourceRef(SourceKind.MEETING, "m1", "Budget review", locator="4:05", quote="cut travel"),
        SourceRef(SourceKind.TASK, "t1", "Book travel", org_id=org),
        SourceRef(SourceKind.FILE, "f1", "Someone else's plan", org_id=uuid.uuid4()),
    ]
    thread = await turn_bench.thread(person)
    turn_bench.model.scripts = [
        calling(("notes__search", '{"query": "budget"}'), ("tasks__search", '{"query": "trip"}')),
        saying("Travel is cut [1][2]."),
    ]

    events = stream_of(await turn_bench.ask(person, thread, "What about travel?", locale="ru"))
    read = [read_back(message) for message in turn_bench.model.calls[1].messages[-2:]]
    shown = [data["sources"] for kind, _, data in events if kind == "sources"]
    row = await fetch_rows(
        turn_bench.connection,
        "SELECT sources FROM agent_messages WHERE id = %s",
        (uuid.UUID(events[0][2]["reply_id"]),),
    )
    history = await turn_bench.http.get(
        f"/v1/agent/threads/{thread}/messages", headers=bearer((HOME, person))
    )
    turn_bench.model.scripts = [saying("Yes.")]
    await turn_bench.ask(person, thread, "Sure?")
    replayed = text_of(turn_bench.model.calls[-1].messages[2])

    expected: list[dict[str, Any]] = [
        {"id": "m1", "kind": "meeting", "title": "Budget review", "space": PERSONAL_SPACE["ru"],
         "locator": "4:05", "quote": "cut travel", "highlight": []},
        {"id": "t1", "kind": "task", "title": "Book travel", "space": "w", "locator": None,
         "quote": "", "highlight": []},
    ]  # fmt: skip
    assert [[cite["n"] for cite in result["sources"]] for result in read] == [[1, 2], [1, 2]]
    assert read[0]["sources"][0] == {
        "n": 1, "kind": "meeting", "id": "m1", "title": "Budget review", "locator": "4:05",
    }  # fmt: skip
    assert shown == [expected]
    kept = cast("list[dict[str, Any]]", row[0]["sources"])
    assert [source["org_id"] for source in kept] == [None, str(org)]
    assert [listed(source) for source in kept] == [listed(source) for source in expected]
    assert history.json()["items"][0]["sources"] == expected
    assert replayed.endswith("Sources of this answer, by number: [1] meeting m1; [2] task t1.")
    assert "Someone else" not in json.dumps(read)


def test_personal_has_a_name_in_every_platform_language() -> None:
    assert set(PERSONAL_SPACE) == {locale.code for locale in LOCALES}
    assert personal_space("xx") == "Personal"
