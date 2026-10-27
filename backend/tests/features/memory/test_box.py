"""The "Ask or update" box and restore: a question is answered, "I moved to…", "forget that I…"
and "remember that…" change the right facts once per key, each restorable for a day, and memory
off is 409 (memory step 7, MM-D3); a change always queues the summary's rewrite, even right
after an open queued one (step 11)."""

import uuid
from typing import Any

import httpx

from shosai.core.kernel.homes import Home
from shosai.features.identity.contracts import Principal
from shosai.features.memory.infrastructure.metrics import SummaryTrigger
from tests.features.billing.people_bench import bearer
from tests.features.memory.summary_bench import SummaryBench

NOTHING: dict[str, object] = {"answer": None, "remember": [], "update": [], "forget": []}


async def say(
    bench: SummaryBench, person: uuid.UUID, message: str, key: str | None = None
) -> httpx.Response:
    """A message in the box."""
    return await bench.http.post(
        "/v1/agent/memory/summary/messages",
        json={"message": message},
        headers=bearer((Home.RU, person)) | {"Idempotency-Key": key or uuid.uuid4().hex},
    )


def changes(answer: httpx.Response) -> list[tuple[str, str, str]]:
    """Each change, its fact's statement and its status."""
    body: dict[str, Any] = answer.json()
    return [
        (item["change"], item["fact"]["statement"], item["fact"]["status"])
        for item in body["changes"]
    ]


async def test_a_question_is_answered_from_the_facts_and_changes_nothing(
    summary_bench: SummaryBench,
) -> None:
    person = uuid.uuid4()
    summary_bench.consents.given.add(person)
    await summary_bench.add(person, [{"statement": "Lives in Moscow"}])
    summary_bench.writer.answers["memory.box"] = [NOTHING | {"answer": "You live in Moscow."}]

    answer = await say(summary_bench, person, "Where do I live?")

    assert answer.status_code == 200, answer.text
    assert answer.json()["answer"] == "You live in Moscow."
    assert answer.json()["changes"] == []
    _, read = summary_bench.writer.asked[0]
    assert "F1 [fact] Lives in Moscow" in read
    assert read.endswith("Where do I live?")
    assert summary_bench.queued == []


async def test_moving_forgetting_and_remembering_change_the_right_facts_once(
    summary_bench: SummaryBench,
) -> None:
    person = uuid.uuid4()
    summary_bench.consents.given.add(person)
    # Ссылки идут по сохранности: последний добавленный факт свежее всех и получает F1.
    await summary_bench.add(
        person, [{"statement": "Kept"}, {"statement": "Smokes"}, {"statement": "Lives in Moscow"}]
    )
    summary_bench.writer.answers["memory.box"] = [
        NOTHING | {
            "update": [{"fact": "F1", "statement": "Lives in Berlin"}],
            "forget": ["F2", "F9"],
            "remember": [{"statement": "Likes tea", "kind": "preference"},
                         {"statement": "kept.", "kind": "fact"}],
        }
    ]  # fmt: skip

    first = await say(summary_bench, person, "I moved to Berlin, quit smoking, like tea", "k1")
    again = await say(summary_bench, person, "I moved to Berlin, quit smoking, like tea", "k1")
    reused = await say(summary_bench, person, "Something else", "k1")

    assert first.status_code == again.status_code == 200, first.text
    assert (
        changes(first)
        == changes(again)
        == [
            ("forgotten", "Smokes", "forgotten"),
            ("updated", "Lives in Berlin", "active"),
            ("remembered", "Likes tea", "active"),
        ]
    )
    assert first.json()["summary"]["stale"]
    assert (reused.status_code, reused.json()["error"]["code"]) == (422, "idempotency_key_reused")
    assert len(summary_bench.writer.asked) == 1
    assert await summary_bench.facts(person) == {
        "Lives in Moscow": ("active", True), "Lives in Berlin": ("active", False),
        "Smokes": ("forgotten", False), "Kept": ("active", False), "Likes tea": ("active", False),
    }  # fmt: skip
    assert len(summary_bench.queued) == 1


async def test_a_change_in_the_box_queues_the_summary_even_right_after_an_open_did(
    summary_bench: SummaryBench,
) -> None:
    person = uuid.uuid4()
    summary_bench.consents.given.add(person)
    await summary_bench.add(person, [{"statement": "Lives in Moscow"}])
    summary_bench.writer.answers["memory.box"] = [
        NOTHING | {"remember": [{"statement": "Likes tea", "kind": "preference"}]}
    ]
    headers = bearer((Home.RU, person))

    await summary_bench.http.get("/v1/agent/memory/summary", headers=headers)
    await say(summary_bench, person, "Remember that I like tea")
    await summary_bench.http.get("/v1/agent/memory/summary", headers=headers)

    assert [trigger for _, trigger in summary_bench.queued] == [
        SummaryTrigger.OPEN,
        SummaryTrigger.BOX,
    ]


async def test_each_change_is_undone_by_restoring_within_a_day(
    summary_bench: SummaryBench,
) -> None:
    person = uuid.uuid4()
    summary_bench.consents.given.add(person)
    await summary_bench.add(person, [{"statement": "Smokes"}, {"statement": "Lives in Moscow"}])
    summary_bench.writer.answers["memory.box"] = [
        NOTHING | {"update": [{"fact": "F1", "statement": "Lives in Berlin"}], "forget": ["F2"]}
    ]
    body = (await say(summary_bench, person, "I moved to Berlin and quit smoking")).json()
    forgotten, updated = body["changes"]
    headers = bearer((Home.RU, person))

    back = await summary_bench.http.post(
        f"/v1/agent/memory/{forgotten['fact']['id']}/restore", headers=headers
    )
    moved_back = await summary_bench.http.post(
        f"/v1/agent/memory/{updated['replaced_id']}/restore", headers=headers
    )
    repeat = await summary_bench.http.post(
        f"/v1/agent/memory/{updated['replaced_id']}/restore", headers=headers
    )
    stranger = await summary_bench.http.post(
        f"/v1/agent/memory/{updated['replaced_id']}/restore",
        headers=bearer((Home.RU, uuid.uuid4())),
    )

    assert (back.status_code, back.json()["status"]) == (200, "active")
    assert (moved_back.status_code, moved_back.json()["statement"]) == (200, "Lives in Moscow")
    assert repeat.json() == moved_back.json()
    assert stranger.status_code == 404
    assert await summary_bench.facts(person) == {
        "Lives in Moscow": ("active", False), "Lives in Berlin": ("forgotten", False),
        "Smokes": ("active", False),
    }  # fmt: skip


async def test_the_box_refuses_with_memory_off_or_without_consent(
    summary_bench: SummaryBench,
) -> None:
    off, refusing = uuid.uuid4(), uuid.uuid4()
    summary_bench.consents.given.add(off)
    await summary_bench.switch.turn(Principal(off, Home.RU, 0), enabled=False)

    answers = [await say(summary_bench, person, "Forget everything") for person in (off, refusing)]

    assert [(answer.status_code, answer.json()["error"]["code"]) for answer in answers] == [
        (409, "memory_off"),
        (403, "consent_required"),
    ]
    assert summary_bench.writer.asked == []
