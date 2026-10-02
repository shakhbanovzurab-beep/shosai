"""The process takes work until a stop request; work that ends by itself fails it."""

import asyncio
from datetime import timedelta

import pytest

from whisperer.composition.features import check_features, contract_slices, feature_checks
from whisperer.composition.process import (
    EXIT_FAILED,
    EXIT_OK,
    OPS_DRAIN,
    STOP_GRACE_PERIOD,
    serve_until_stopped,
)
from whisperer.composition.roles import PUBLIC_DRAIN
from whisperer.composition.startup import StartFailedError, start_step
from whisperer.core.config.gate import GateViolation
from whisperer.core.config.loading import Settings
from whisperer.core.features import FeatureModule
from whisperer.core.health.readiness import ProcessPhase, Readiness
from whisperer.core.observability.tracing import SHUTDOWN_BUDGET_SECONDS
from whisperer.core.tasks.worker import DRAIN_TIMEOUT


async def runs_until_cancelled() -> None:
    """Work that only a stop ends."""
    await asyncio.Event().wait()


async def ends_at_once() -> None:
    """Work that ends by itself."""


async def test_a_stop_request_drains_and_exits_cleanly() -> None:
    readiness, stop = Readiness(), asyncio.Event()
    work = asyncio.create_task(runs_until_cancelled())
    serving = asyncio.create_task(serve_until_stopped(readiness, stop, (), (work,)))
    await asyncio.sleep(0.01)
    phase_while_serving = readiness.phase
    stop.set()

    code = await serving
    work.cancel()

    assert (phase_while_serving, readiness.phase, code) == (
        ProcessPhase.READY,
        ProcessPhase.DRAINING,
        EXIT_OK,
    )


async def test_work_that_ends_by_itself_fails_the_process() -> None:
    readiness, stop = Readiness(), asyncio.Event()
    work = asyncio.create_task(ends_at_once(), name="worker:default")

    code = await serve_until_stopped(readiness, stop, (), (work,))

    assert (code, readiness.phase) == (EXIT_FAILED, ProcessPhase.DRAINING)


async def test_a_stop_requested_during_the_start_never_makes_the_process_ready() -> None:
    readiness, stop = Readiness(), asyncio.Event()
    readiness.drain()
    stop.set()

    code = await serve_until_stopped(readiness, stop, (), (asyncio.create_task(ends_at_once()),))

    assert (code, readiness.phase) == (EXIT_OK, ProcessPhase.DRAINING)


def test_a_failed_step_is_named_and_keeps_its_cause() -> None:
    cause = OSError("порт занят")

    with pytest.raises(StartFailedError) as raised, start_step("ops"):
        raise cause

    assert (raised.value.step, raised.value.__cause__) == ("ops", cause)


def test_a_failure_inside_a_nested_step_keeps_the_inner_name() -> None:
    with pytest.raises(StartFailedError) as raised, start_step("platform"), start_step("events"):
        raise ValueError

    assert raised.value.step == "events"


def test_the_drain_and_the_close_fit_the_stop_grace_period() -> None:
    longest_drain = max(PUBLIC_DRAIN, DRAIN_TIMEOUT)
    close = OPS_DRAIN + timedelta(seconds=SHUTDOWN_BUDGET_SECONDS)

    assert longest_drain + close < STOP_GRACE_PERIOD


def test_the_slices_add_their_checks_and_their_contract_slices() -> None:
    def billing_dev_mode_off(_settings: Settings) -> list[GateViolation]:
        return []

    billing = FeatureModule(
        name="billing", contract_slice="S03", production_checks=(billing_dev_mode_off,)
    )

    assert feature_checks([billing]) == [billing_dev_mode_off]
    assert contract_slices([billing]) == {"F1", "S03"}
    with pytest.raises(ValueError, match="billing"):
        check_features([billing, billing])
