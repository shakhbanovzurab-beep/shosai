"""The minute's sweep of cards nobody decides or carries out, a deleted thread's cards, and the
audit of an item's effect (agent step 9a; Leo §8.4 rules 2, 3, 6)."""

import asyncio
import uuid
from datetime import UTC, datetime

from shosai.core.agent_tools.events import ActionItemExecuted
from shosai.core.events.subscriptions import ReceivedEvent
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.agent.application.action_audit import audit_item
from tests.features.agent.action_bench import ActionBench
from tests.features.agent.turn_bench import HOME
from tests.features.billing.people_bench import bearer

STATUS = "SELECT status, items FROM agent_actions WHERE id = %s"
AUDITED = "SELECT event, code FROM agent_audit WHERE action_id = %s ORDER BY created_at"
RUN = "SELECT status, outcome_code FROM agent_runs WHERE id = %s"


async def test_a_card_past_its_hour_expires_and_closes_its_run(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    action_id = uuid.UUID(turn["card"]["id"])
    await action_bench.move(
        "UPDATE agent_actions SET expires_at = now() - interval '1 second' WHERE id = %s", action_id
    )

    settled = await action_bench.sweep()
    action = (await action_bench.rows(STATUS, action_id))[0]
    run = (await action_bench.rows(RUN, uuid.UUID(turn["run_id"])))[0]

    assert settled == 1
    assert action["status"] == "expired"
    assert (run["status"], run["outcome_code"]) == ("completed", "decided")
    assert [row["event"] for row in await action_bench.rows(AUDITED, action_id)] == [
        "proposed", "expired",
    ]  # fmt: skip


async def test_an_approval_nobody_claims_is_handed_over_again_then_fails_unstarted(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    action_id = uuid.UUID(turn["card"]["id"])
    action_bench.queue.hold = True
    waiting = await action_bench.decide(person, turn["card"], "approve")
    shift = "UPDATE agent_actions SET approved_at = now() - %s::interval WHERE id = %s"

    await action_bench.move(shift, "2 minutes", action_id)
    await action_bench.sweep()
    handed = len(action_bench.queue.sent)
    await action_bench.move(shift, "11 minutes", action_id)
    await action_bench.sweep()
    action = (await action_bench.rows(STATUS, action_id))[0]

    assert waiting.json()["status"] == "executing"
    assert handed == 2
    assert action["status"] == "failed"
    assert [(item["state"], item["code"]) for item in action["items"]] == [
        ("failed", "not_started")
    ]
    assert action_bench.turns.tools.executed == []


async def test_an_executor_lost_mid_effect_leaves_the_outcome_unknown_and_never_retries(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    action_id = uuid.UUID(turn["card"]["id"])
    action_bench.turns.tools.effect_gate.clear()
    await action_bench.decide(person, turn["card"], "approve")
    executor = action_bench.queue.running.pop()
    executor.cancel()
    await asyncio.gather(executor, return_exceptions=True)
    await action_bench.move(
        "UPDATE agent_actions SET updated_at = now() - interval '6 minutes' WHERE id = %s",
        action_id,
    )

    await action_bench.sweep()
    action_bench.turns.tools.effect_gate.set()
    await action_bench.execution.run(HOME, person, action_id)
    action = (await action_bench.rows(STATUS, action_id))[0]

    assert action["status"] == "outcome_unknown"
    assert [(item["state"], item["code"]) for item in action["items"]] == [
        ("outcome_unknown", "executor_lost")
    ]
    assert action_bench.turns.tools.executed == []
    assert [row["event"] for row in await action_bench.rows(AUDITED, action_id)][-1] == (
        "outcome_unknown"
    )


async def test_a_deleted_thread_s_card_can_no_longer_be_approved(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    action_id = uuid.UUID(turn["card"]["id"])

    deleted = await action_bench.turns.http.delete(
        f"/v1/agent/threads/{turn['thread']}", headers=bearer((HOME, person))
    )
    late = await action_bench.decide(person, turn["card"], "approve")
    run = (await action_bench.rows(RUN, uuid.UUID(turn["run_id"])))[0]

    assert deleted.status_code == 204
    assert (await action_bench.rows(STATUS, action_id))[0]["status"] == "superseded"
    assert late.status_code == 409
    assert run["status"] == "cancelled"
    assert [row["event"] for row in await action_bench.rows(AUDITED, action_id)] == [
        "proposed", "superseded",
    ]  # fmt: skip


async def test_an_item_s_effect_is_audited_once_however_often_it_is_delivered(
    action_bench: ActionBench,
) -> None:
    person, action_id = uuid.uuid4(), uuid.uuid4()
    received = ReceivedEvent(
        ActionItemExecuted(item_key=f"{action_id}:0", tool="tasks.create", targets=2),
        uuid.uuid4(), 1, datetime.now(UTC), TenancyScope(HOME, person),
    )  # fmt: skip

    for _ in range(2):
        async with action_bench.turns.homes.transactions.begin(TenancyScope(HOME, person)) as s:
            await audit_item(s, received)
    rows = await action_bench.rows(
        "SELECT event, item_key, tool_name, targets FROM agent_audit WHERE action_id = %s",
        action_id,
    )

    assert rows == [
        {"event": "executed", "item_key": f"{action_id}:0", "tool_name": "tasks.create",
         "targets": 2}
    ]  # fmt: skip
