"""Leo's writes go through the Action Gateway only (agent step 9a; Leo §5.3, §8.4).

A write call becomes a card and pauses the run; the person approves it once, with the card's
nonce, before its hour runs out, and the write takes effect once through its slice; a rejection,
a wrong nonce or a card past its hour changes nothing. Every decision closes the paused run
with a note the next turn reads.
"""

import uuid

from tests.features.agent.action_bench import WRITE, ActionBench
from tests.features.agent.tool_doubles import calling, saying
from tests.features.agent.turn_bench import HOME, stream_of
from tests.features.billing.people_bench import bearer

ACTION_ROW = (
    "SELECT status, items, friction, taint, nonce, resolved_at FROM agent_actions WHERE id = %s"
)
RUN_ROW = "SELECT status, outcome_code, ended_at FROM agent_runs WHERE id = %s"
AUDIT = "SELECT event, via, code FROM agent_audit WHERE action_id = %s ORDER BY created_at, event"
NOTES = (
    "SELECT role, text, digest, action_ids FROM agent_messages"
    " WHERE run_id = %s AND role = 'server'"
)


async def test_a_write_call_pauses_the_run_with_a_card_and_changes_nothing(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()

    turn = await action_bench.paused_turn(person)
    card, events = turn["card"], turn["events"]
    action = (await action_bench.rows(ACTION_ROW, uuid.UUID(card["id"])))[0]
    run = (await action_bench.rows(RUN_ROW, uuid.UUID(turn["run_id"])))[0]

    assert [kind for kind, _, _ in events] == [
        "run.started", "step.started", "step.completed", "action.proposed", "run.paused",
    ]  # fmt: skip
    assert events[-1][2] == {"action_id": card["id"]}
    assert (card["status"], card["tool"], card["warning"], card["taint"]) == (
        "proposed", "tasks.create", False, None,
    )  # fmt: skip
    assert (action["status"], action["friction"], action["taint"]) == ("proposed", 0, 0)
    assert action["items"][0]["plan"] == {"query": "Call Anna"}
    assert [field["name"] for field in action["items"][0]["fields"]] == ["query"]
    assert (run["status"], run["outcome_code"], run["ended_at"]) == ("paused", "paused", None)
    assert action_bench.turns.tools.executed == []
    assert await action_bench.rows(AUDIT, uuid.UUID(card["id"])) == [
        {"event": "proposed", "via": None, "code": None}
    ]


async def test_an_approved_card_takes_effect_once_and_tells_its_thread(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    card = turn["card"]

    approved = await action_bench.decide(person, card, "approve")
    again = await action_bench.decide(person, card, "approve")
    await action_bench.queue.settle()
    tail = await action_bench.turns.http.get(
        f"/v1/agent/runs/{turn['run_id']}/events",
        headers=bearer((HOME, person)) | {"Last-Event-ID": str(turn["events"][-1][1])},
    )
    note = (await action_bench.rows(NOTES, uuid.UUID(turn["run_id"])))[0]
    run = (await action_bench.rows(RUN_ROW, uuid.UUID(turn["run_id"])))[0]

    assert approved.status_code == 200, approved.text
    assert (approved.json()["status"], approved.json()["run_id"]) == ("succeeded", turn["run_id"])
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "action_not_pending"
    assert action_bench.turns.tools.executed == [f"{card['id']}:0"]
    assert [kind for kind, _, _ in stream_of(tail)][:2] == ["action.updated", "action.updated"]
    assert [data["action"]["status"] for kind, _, data in stream_of(tail)[:2]] == [
        "executing", "succeeded",
    ]  # fmt: skip
    assert (run["status"], run["outcome_code"]) == ("completed", "answered")
    assert note["text"] == ""
    assert note["action_ids"] == [uuid.UUID(card["id"])]
    assert note["digest"]["text"].endswith("with tasks.create was approved and done.")
    assert [row["event"] for row in await action_bench.rows(AUDIT, uuid.UUID(card["id"]))] == [
        "proposed", "approved",
    ]  # fmt: skip


async def test_a_rejected_wrong_or_expired_card_changes_nothing(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    rejected = (await action_bench.paused_turn(person))["card"]
    expired = (await action_bench.paused_turn(person))["card"]
    await action_bench.move(
        "UPDATE agent_actions SET expires_at = now() - interval '1 second' WHERE id = %s",
        uuid.UUID(expired["id"]),
    )

    wrong = await action_bench.decide(person, rejected, "approve", nonce="not-the-card")
    stranger = await action_bench.decide(uuid.uuid4(), rejected, "approve")
    refused = await action_bench.decide(person, rejected, "reject")
    late = await action_bench.decide(person, expired, "approve")
    statuses = [
        (await action_bench.rows(ACTION_ROW, uuid.UUID(card["id"])))[0]["status"]
        for card in (rejected, expired)
    ]

    assert (wrong.status_code, wrong.json()["error"]["code"]) == (409, "action_not_pending")
    assert (stranger.status_code, stranger.json()["error"]["code"]) == (404, "action_not_found")
    assert (refused.status_code, refused.json()["status"]) == (200, "rejected")
    assert (late.status_code, late.json()["error"]["code"]) == (409, "action_not_pending")
    assert statuses == ["rejected", "expired"]
    assert action_bench.turns.tools.executed == []


async def test_the_next_turn_reads_what_became_of_the_card(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    await action_bench.decide(person, turn["card"], "reject")
    action_bench.turns.model.calls.clear()
    action_bench.turns.model.scripts = [saying("Fine.")]

    await action_bench.turns.ask(person, turn["thread"], "Never mind.")
    texts = [
        "".join(getattr(part, "text", "") for part in message.parts)
        for message in action_bench.turns.model.calls[0].messages
    ]

    assert any(
        text.endswith("the change you proposed with tasks.create was rejected by the person.")
        for text in texts
    )


async def test_a_second_write_in_a_round_waits_and_a_refused_plan_is_the_model_s(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()
    thread = await action_bench.turns.thread(person)
    action_bench.turns.model.calls.clear()
    action_bench.turns.model.scripts = [calling(WRITE, WRITE), saying("One card.")]
    two = stream_of(await action_bench.turns.ask(person, thread, "Two tasks."))
    action_bench.turns.tools.refuse_plan = True
    action_bench.turns.model.calls.clear()
    action_bench.turns.model.scripts = [calling(WRITE), saying("I may not.")]
    refused = stream_of(await action_bench.turns.ask(person, thread, "Again."))

    assert [kind for kind, _, _ in two].count("action.proposed") == 1
    assert two[-1][0] == "run.paused"
    assert "action.proposed" not in [kind for kind, _, _ in refused]
    assert refused[-1][0] == "run.completed"
    assert "step.failed" in [kind for kind, _, _ in refused]
