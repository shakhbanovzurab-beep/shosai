"""A person's threads and their history on `/v1/agent/threads*` (agent step 4)."""

import uuid
from datetime import timedelta

from tests.features.agent.thread_bench import ThreadBench
from tests.harness.connections import fetch_value


async def codes(bench: ThreadBench, person: uuid.UUID, thread: str) -> list[tuple[int, str]]:
    """What each route of a thread answers the person: status and error code."""
    answers = [
        await bench.call(person, "GET", f"/v1/agent/threads/{thread}"),
        await bench.call(person, "PATCH", f"/v1/agent/threads/{thread}", json={"title": "Mine"}),
        await bench.call(person, "GET", f"/v1/agent/threads/{thread}/messages"),
        await bench.call(person, "DELETE", f"/v1/agent/threads/{thread}"),
    ]
    return [(answer.status_code, answer.json()["error"]["code"]) for answer in answers]


async def test_a_thread_is_made_once_per_key_untitled_in_its_space(
    thread_bench: ThreadBench,
) -> None:
    person, key = uuid.uuid4(), {"Idempotency-Key": "new-chat-1"}
    body = {"scope": {"kind": "personal"}}

    made = await thread_bench.call(person, "POST", "/v1/agent/threads", json=body, headers=key)
    again = await thread_bench.call(person, "POST", "/v1/agent/threads", json=body, headers=key)
    other = await thread_bench.call(
        person, "POST", "/v1/agent/threads",
        json={"scope": {"kind": "workspace", "workspace_id": str(uuid.uuid4())}}, headers=key,
    )  # fmt: skip
    listed = await thread_bench.call(person, "GET", "/v1/agent/threads?scope=personal")

    assert (made.status_code, again.json()) == (201, made.json())
    assert made.json()["title"] is None
    assert made.json()["scope"] == {"kind": "personal", "workspace_id": None, "hub_id": None}
    assert other.json()["error"]["code"] == "idempotency_key_reused"
    assert [item["id"] for item in listed.json()["items"]] == [made.json()["id"]]


async def test_a_title_is_the_person_s_and_a_deleted_thread_is_gone(
    thread_bench: ThreadBench,
) -> None:
    person = uuid.uuid4()
    thread = await thread_bench.thread(person)
    await thread_bench.message(person, thread, "user", thread_bench.clock.now, "Budget?")

    renamed = await thread_bench.call(
        person, "PATCH", f"/v1/agent/threads/{thread}", json={"title": "  Budget \n review "}
    )
    empty = await thread_bench.call(
        person, "PATCH", f"/v1/agent/threads/{thread}", json={"title": "   "}
    )
    deleted = await thread_bench.call(person, "DELETE", f"/v1/agent/threads/{thread}")

    assert renamed.json()["title"] == "Budget review"
    assert (empty.status_code, empty.json()["error"]["code"]) == (422, "title_invalid")
    assert deleted.status_code == 204
    assert await codes(thread_bench, person, thread) == [(404, "thread_not_found")] * 4
    left = await fetch_value(
        thread_bench.connection,
        "SELECT count(*) FROM agent_messages WHERE thread_id = %s",
        (uuid.UUID(thread),),
    )
    assert left == 0


async def test_another_person_s_thread_is_not_found_on_every_route(
    thread_bench: ThreadBench,
) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    thread = await thread_bench.thread(owner)

    refused = await codes(thread_bench, stranger, thread)
    listed = await thread_bench.call(stranger, "GET", "/v1/agent/threads?scope=personal")
    still = await thread_bench.call(owner, "GET", f"/v1/agent/threads/{thread}")

    assert refused == [(404, "thread_not_found")] * 4
    assert listed.json() == {"items": [], "next_cursor": None}
    assert (still.status_code, still.json()["title"]) == (200, None)


async def test_a_scope_names_a_space_the_person_has(thread_bench: ThreadBench) -> None:
    person, foreign = uuid.uuid4(), uuid.uuid4()
    key = {"Idempotency-Key": uuid.uuid4().hex}
    cases = [
        ("GET", "/v1/agent/threads?scope=hub", None),
        ("POST", "/v1/agent/threads", {"scope": {"kind": "hub"}}),
        ("GET", "/v1/agent/threads?scope=workspace", None),
        ("GET", f"/v1/agent/threads?scope=personal&workspace_id={foreign}", None),
        (
            "POST",
            "/v1/agent/threads",
            {"scope": {"kind": "workspace", "workspace_id": str(foreign)}},
        ),
        ("POST", "/v1/agent/threads", {"scope": {"kind": "personal"}, "title": "x"}),
    ]
    answers = [
        await thread_bench.call(person, method, path, json=body, headers=key)
        for method, path, body in cases
    ]
    foreign_list = await thread_bench.call(
        person, "GET", f"/v1/agent/threads?scope=workspace&workspace_id={foreign}"
    )

    assert [(answer.status_code, answer.json()["error"]["code"]) for answer in answers] == [
        (422, "scope_unavailable"),
        (422, "scope_unavailable"),
        (422, "scope_invalid"),
        (422, "scope_invalid"),
        (404, "workspace_not_found"),
        (422, "validation_error"),
    ]
    assert foreign_list.json() == {"items": [], "next_cursor": None}


async def test_threads_page_by_newest_activity(thread_bench: ThreadBench) -> None:
    person = uuid.uuid4()
    made = []
    for _ in range(3):
        made.append(await thread_bench.thread(person))
        thread_bench.clock.advance(timedelta(minutes=1))

    first = await thread_bench.call(person, "GET", "/v1/agent/threads?scope=personal&limit=2")
    cursor = first.json()["next_cursor"]
    second = await thread_bench.call(
        person, "GET", f"/v1/agent/threads?scope=personal&limit=2&cursor={cursor}"
    )
    broken = await thread_bench.call(
        person, "GET", "/v1/agent/threads?scope=personal&cursor=not-a-cursor"
    )

    assert [item["id"] for item in first.json()["items"]] == made[:0:-1]
    assert [item["id"] for item in second.json()["items"]] == [made[0]]
    assert second.json()["next_cursor"] is None
    assert broken.json()["error"]["code"] == "invalid_cursor"


async def test_history_pages_newest_first_without_the_model_s_rounds(
    thread_bench: ThreadBench,
) -> None:
    person = uuid.uuid4()
    thread = await thread_bench.thread(person)
    moment = thread_bench.clock.now
    shown = []
    for offset, role in enumerate(("user", "round", "tool", "assistant", "server", "user")):
        written = await thread_bench.message(
            person, thread, role, moment + timedelta(seconds=offset), f"{role} {offset}"
        )
        if role not in {"round", "tool"}:
            shown.append(written)

    path = f"/v1/agent/threads/{thread}/messages?limit=3"
    first = await thread_bench.call(person, "GET", path)
    rest = await thread_bench.call(person, "GET", f"{path}&cursor={first.json()['next_cursor']}")

    pages = [item["id"] for item in first.json()["items"] + rest.json()["items"]]
    assert pages == shown[::-1]
    assert rest.json()["next_cursor"] is None
    assert first.json()["items"][1] == {
        "id": shown[2], "role": "server", "text": "server 4", "status": None,
        "created_at": first.json()["items"][1]["created_at"], "duration_ms": None, "steps": [],
        "sources": [], "actions": [], "artifacts": [], "feedback": None, "attachments": [],
    }  # fmt: skip
    assert first.json()["items"][2]["status"] == "done"
