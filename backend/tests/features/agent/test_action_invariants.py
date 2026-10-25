"""The watch over Leo's actions (agent step 9a2; Leo L-N5, §16.3, §16.4).

The hourly check counts, per home, the items its audit shows executed twice under their key and
those executed with no `approved` row, and both stay 0 for actions that went through the
gateway. An approved action that ends within 30 s counts for its objective. A run whose resume
never came closes at the minute's sweep without its epilogue; one whose epilogue proposed the
next card waits for that card.
"""

import uuid
from typing import Final

from shosai.features.agent.application.action_invariants import ActionInvariants
from shosai.features.agent.infrastructure.action_metrics import (
    APPROVED_ACTIONS,
    EXECUTED_TWICE,
    EXECUTED_UNAPPROVED,
)
from shosai.features.agent.infrastructure.run_keys import checkpoint_key
from tests.features.agent.action_bench import WRITE, ActionBench
from tests.features.agent.tool_doubles import calling, saying
from tests.features.agent.turn_bench import HOME

AUDITED: Final = (
    "INSERT INTO agent_audit (id, created_at, user_id, action_id, item_key, tool_name, event)"
    " VALUES (gen_random_uuid(), now(), %s, %s, %s, 'tasks.create', %s)"
)
RUN_ROW: Final = "SELECT status, outcome_code FROM agent_runs WHERE id = %s"
STALE: Final = "UPDATE agent_actions SET updated_at = now() - interval '6 minutes' WHERE id = %s"


async def test_the_check_finds_items_executed_twice_or_unapproved(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()
    approved_card = (await action_bench.paused_turn(person))["card"]
    await action_bench.decide(person, approved_card, "approve")
    await action_bench.queue.settle()
    async with action_bench.turns.sweeping() as transactions:
        check = ActionInvariants(transactions, action_bench.parts[2])
        clean = await check.check(HOME)
        doubled, forged = uuid.UUID(approved_card["id"]), uuid.uuid4()
        await action_bench.move(AUDITED, person, doubled, f"{doubled}:0", "executed")
        await action_bench.move(AUDITED, person, doubled, f"{doubled}:0", "executed")
        await action_bench.move(AUDITED, person, forged, f"{forged}:0", "executed")
        broken = await check.check(HOME)
    sample = action_bench.registry.get_sample_value

    assert clean == (0, 0)
    assert broken == (1, 1)
    assert sample(EXECUTED_TWICE, {"home": HOME.value}) == 1
    assert sample(EXECUTED_UNAPPROVED, {"home": HOME.value}) == 1
    assert sample(APPROVED_ACTIONS, {"result": "in_time"}) == 1


async def test_a_run_whose_resume_never_came_closes_at_the_sweep(
    action_bench: ActionBench,
) -> None:
    person = uuid.uuid4()
    action_bench.queue.hold_resumes = True
    turn = await action_bench.paused_turn(person)
    run_id = uuid.UUID(turn["run_id"])
    await action_bench.decide(person, turn["card"], "approve")
    await action_bench.queue.settle()
    waiting = (await action_bench.rows(RUN_ROW, run_id))[0]
    await action_bench.move(STALE, uuid.UUID(turn["card"]["id"]))

    await action_bench.sweep()
    run = (await action_bench.rows(RUN_ROW, run_id))[0]

    assert waiting["status"] == "paused"
    assert (run["status"], run["outcome_code"]) == ("completed", "checkpoint_lost")
    assert not await action_bench.turns.valkey.exists(checkpoint_key(run_id))


async def test_a_run_paused_on_its_next_card_waits_for_it(action_bench: ActionBench) -> None:
    person = uuid.uuid4()
    turn = await action_bench.paused_turn(person)
    run_id = uuid.UUID(turn["run_id"])
    # Модель отвечает по номеру вызова: первый уже был, эпилог предлагает следующую запись.
    action_bench.turns.model.scripts = [calling(WRITE), calling(WRITE), saying("Later.")]
    await action_bench.decide(person, turn["card"], "approve")
    await action_bench.queue.settle()
    await action_bench.move(STALE, uuid.UUID(turn["card"]["id"]))

    await action_bench.sweep()
    run = (await action_bench.rows(RUN_ROW, run_id))[0]
    cards = await action_bench.rows("SELECT status FROM agent_actions WHERE run_id = %s", run_id)

    assert sorted(card["status"] for card in cards) == ["proposed", "succeeded"]
    assert run["status"] == "paused"
    assert await action_bench.turns.valkey.exists(checkpoint_key(run_id))
