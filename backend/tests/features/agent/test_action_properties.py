"""The Action Gateway's invariants on real PostgreSQL (agent step 9a; Leo §8.4, §11.4).

Concurrent approvals of one card have one winner and its write takes effect once; an executor
killed at any step never applies an item twice, never applies one that was not approved, and
the sweep ends the action with what is known; a card past its hour is never approved.
"""

import asyncio
import contextlib
import uuid
from typing import Final

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from shosai.features.agent.application.action_execution import ActionExecution, Claimed
from shosai.features.agent.application.egress_calls import EgressCalls
from shosai.features.agent.application.result_pages import ResultPages
from shosai.features.agent.domain.action_items import ActionItem
from tests.features.agent.action_bench import ActionBench
from tests.features.agent.turn_bench import HOME

GATEWAY_PROPERTY = settings(
    max_examples=10,
    deadline=None,
    # Каждый пример заводит новый тред и карточку; фикстуры очищают дома и Valkey после теста.
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
STATUS: Final = "SELECT status, items FROM agent_actions WHERE id = %s"
APPROVE: Final = (
    "UPDATE agent_actions SET status = 'approved', approved_at = now(), approved_via = 'web',"
    " updated_at = now() WHERE id = %s"
)
LAPSE: Final = "UPDATE agent_actions SET updated_at = now() - interval '6 minutes' WHERE id = %s"
# Где «умирает» исполнитель: после захвата, после записи «исполняется», после эффекта, до конца.
CRASHES: Final = ("claimed", "started", "applied", "stored")
ENDS: Final = {
    "claimed": ("failed", []),
    "started": ("outcome_unknown", []),
    "applied": ("outcome_unknown", ["applied"]),
    "stored": ("succeeded", ["applied"]),
}


class CrashError(Exception):
    """The executor's process died here."""


class Crashing(ActionExecution):
    """An executor that dies at one point of its work."""

    def __init__(self, bench: ActionBench, at: str) -> None:
        _, paused, metrics = bench.parts
        transactions = bench.turns.homes.transactions
        egress = EgressCalls(ResultPages(transactions, bench.turns.ports))
        super().__init__(transactions, (bench.turns.catalog, paused, metrics, egress))
        self._at = at
        self._stores = 0

    async def _store(self, claimed: Claimed, items: list[ActionItem]) -> bool:
        self._stores += 1
        if self._at == "claimed" or (self._at == "applied" and self._stores == 2):
            raise CrashError
        return await super()._store(claimed, items)

    async def _apply(self, claimed: Claimed, item: ActionItem, index: int) -> ActionItem:
        if self._at == "started":
            raise CrashError
        return await super()._apply(claimed, item, index)

    async def _finish(self, claimed: Claimed, items: list[ActionItem]) -> None:
        if self._at == "stored":
            raise CrashError
        await super()._finish(claimed, items)


@GATEWAY_PROPERTY
@given(deciders=st.integers(2, 8))
async def test_concurrent_approvals_have_one_winner_and_one_effect(
    action_bench: ActionBench, deciders: int
) -> None:
    person = uuid.uuid4()
    card = (await action_bench.paused_turn(person))["card"]
    executed_before = len(action_bench.turns.tools.executed)

    answers = await asyncio.gather(
        *(action_bench.decide(person, card, "approve") for _ in range(deciders))
    )
    await action_bench.queue.settle()

    assert sorted(answer.status_code for answer in answers) == [200] + [409] * (deciders - 1)
    assert action_bench.turns.tools.executed[executed_before:] == [f"{card['id']}:0"]


@GATEWAY_PROPERTY
@given(crash=st.sampled_from(CRASHES), deliveries=st.integers(0, 2))
async def test_a_killed_executor_never_applies_twice_or_unapproved(
    action_bench: ActionBench, crash: str, deliveries: int
) -> None:
    person = uuid.uuid4()
    card = (await action_bench.paused_turn(person))["card"]
    action_id = uuid.UUID(card["id"])
    executed_before = len(action_bench.turns.tools.executed)
    await action_bench.execution.run(HOME, person, action_id)
    unapproved = action_bench.turns.tools.executed[executed_before:]
    await action_bench.move(APPROVE, action_id)

    with contextlib.suppress(CrashError):
        await Crashing(action_bench, crash).run(HOME, person, action_id)
    await action_bench.move(LAPSE, action_id)
    await action_bench.sweep()
    for _ in range(deliveries):
        await action_bench.execution.run(HOME, person, action_id)
    # Эпилог после конца действия идёт в фоне: он доигрывает свой сценарий до следующего примера.
    await action_bench.queue.settle()
    status = (await action_bench.rows(STATUS, action_id))[0]["status"]
    applied = action_bench.turns.tools.executed[executed_before:]

    expected_status, expected_applied = ENDS[crash]
    assert unapproved == []
    assert status == expected_status
    assert ["applied"] * len(applied) == expected_applied
    assert set(applied) <= {f"{action_id}:0"}


@GATEWAY_PROPERTY
@given(seconds_past=st.integers(0, 3_600))
async def test_a_card_past_its_hour_is_never_approved(
    action_bench: ActionBench, seconds_past: int
) -> None:
    person = uuid.uuid4()
    card = (await action_bench.paused_turn(person))["card"]
    action_id = uuid.UUID(card["id"])
    await action_bench.move(
        "UPDATE agent_actions SET expires_at = now() - make_interval(secs => %s) WHERE id = %s",
        seconds_past, action_id,
    )  # fmt: skip
    executed_before = len(action_bench.turns.tools.executed)

    answer = await action_bench.decide(person, card, "approve")
    await action_bench.queue.settle()

    assert answer.status_code == 409
    assert (await action_bench.rows(STATUS, action_id))[0]["status"] == "expired"
    assert action_bench.turns.tools.executed[executed_before:] == []
