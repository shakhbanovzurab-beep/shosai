"""How a finished run is settled, and which held deliveries keep their leases."""

import asyncio
from datetime import timedelta

import pytest
from taskiq import TaskiqMessage

from shosai.core.tasks.declaration import RETRY_TRANSIENT, TaskDeclaration, TaskKind
from shosai.core.tasks.deliveries import (
    Acknowledge,
    Delivery,
    HeldDeliveries,
    LeavePending,
    MoveToDeadLetter,
    RetryLater,
    decide,
)
from shosai.core.tasks.timing import Backoff
from tests.core.tasks.workbench import Probe, declare

RETRIED = declare("probe.retried", retry=RETRY_TRANSIENT)
ONCE = declare("probe.once")
TICK = declare("probe.tick", kind=TaskKind.TICK)
BACKOFF = Backoff(first=timedelta(seconds=4), ceiling=timedelta(seconds=60))


def delivery_of(task: TaskDeclaration[Probe], number: int = 1, task_id: str = "t-1") -> Delivery:
    return Delivery("1-0", task_id, task, number, taken_at=0.0)


def message_of(delivery: Delivery) -> TaskiqMessage:
    return TaskiqMessage(
        task_id=delivery.task_id,
        task_name=delivery.task.name,
        labels={},
        args=[],
        kwargs={"payload": Probe(note="x").model_dump(mode="json")},
    )


def settle(delivery: Delivery, error: BaseException | None) -> tuple[object, str]:
    return decide(delivery, message_of(delivery), error, BACKOFF)


def test_a_successful_run_is_acknowledged() -> None:
    assert settle(delivery_of(ONCE), None) == (Acknowledge(), "succeeded")


def test_a_listed_failure_before_the_last_delivery_is_retried_after_a_pause() -> None:
    settlement, outcome = settle(delivery_of(RETRIED, number=2), ConnectionError())

    assert outcome == "retried"
    assert isinstance(settlement, RetryLater)
    assert timedelta(seconds=4) <= settlement.delay <= timedelta(seconds=8)


@pytest.mark.parametrize(
    ("task", "number", "error"),
    [(RETRIED, 5, ConnectionError()), (RETRIED, 1, ValueError()), (ONCE, 1, ConnectionError())],
)
def test_the_last_delivery_or_an_unlisted_failure_goes_to_the_dead_letter(
    task: TaskDeclaration[Probe], number: int, error: Exception
) -> None:
    settlement, outcome = settle(delivery_of(task, number=number), error)

    assert outcome == "dead_lettered"
    assert isinstance(settlement, MoveToDeadLetter)
    assert settlement.entry.deliveries == number
    assert settlement.entry.error_type == f"builtins.{type(error).__name__}"


def test_a_failed_tick_is_dropped_for_the_next_tick() -> None:
    assert settle(delivery_of(TICK), RuntimeError()) == (Acknowledge(), "dropped")


@pytest.mark.parametrize("error", [asyncio.CancelledError(), KeyboardInterrupt()])
def test_an_interrupted_run_stays_pending_for_another_worker(error: BaseException) -> None:
    assert settle(delivery_of(RETRIED), error) == (LeavePending(), "interrupted")


def test_one_delivery_per_task_is_held() -> None:
    held = HeldDeliveries()
    first = delivery_of(ONCE)

    held.take(first)
    with pytest.raises(ValueError, match="уже удерживается"):
        held.take(delivery_of(ONCE))
    assert held.get("t-1") is first
    held.release(first)
    assert held.get("t-1") is None
    assert len(held) == 0


def test_a_lost_delivery_is_kept_until_settled_but_no_longer_renewed() -> None:
    held = HeldDeliveries(clock=lambda: 0.0)
    lost, kept = delivery_of(ONCE, task_id="lost"), delivery_of(ONCE, task_id="kept")
    held.take(lost)
    held.take(kept)

    assert held.lose(lost)
    assert not held.lose(lost)

    renew, capped = held.due_for_renewal()
    assert renew == [kept]
    assert capped == []
    assert held.get("lost") is lost


def test_a_delivery_held_past_its_deadline_and_grace_is_capped_once() -> None:
    now = [0.0]
    held = HeldDeliveries(clock=lambda: now[0])
    delivery = delivery_of(ONCE)
    held.take(delivery)

    now[0] = ONCE.hold_limit.total_seconds() + 1
    assert held.due_for_renewal() == ([], [delivery])
    assert held.due_for_renewal() == ([], [])
    assert held.get(delivery.task_id) is delivery
