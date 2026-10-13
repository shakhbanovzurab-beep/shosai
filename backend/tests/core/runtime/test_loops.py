"""Scheduled loops: at start, then per interval; a failed iteration is counted and survived."""

import asyncio
import time
from collections.abc import Callable
from datetime import timedelta

import pytest
from prometheus_client import CollectorRegistry

from shosai.core.runtime.loops import LoopMetrics, LoopRunner, ScheduledLoop
from tests.core.observability.capture import captured_logs

QUICK = timedelta(milliseconds=30)
WAIT_SECONDS = 5.0


class Calls:
    """How often a loop's work ran, and what it does each time."""

    def __init__(self, fail_first: int = 0, hang_first: int = 0) -> None:
        self.count = 0
        self._fail_first = fail_first
        self._hang_first = hang_first

    async def __call__(self) -> None:
        self.count += 1
        if self.count <= self._hang_first:
            await asyncio.sleep(60)
        if self.count <= self._fail_first:
            message = "итерация сломана нарочно"
            raise RuntimeError(message)


async def eventually(holds: Callable[[], bool]) -> None:
    """Wait until `holds` is true, or fail the test."""
    deadline = time.monotonic() + WAIT_SECONDS
    while not holds():
        if time.monotonic() > deadline:
            pytest.fail("условие не выполнилось", pytrace=False)
        await asyncio.sleep(0.01)


def sample(registry: CollectorRegistry, name: str, loop: str, **labels: str) -> float:
    """A loop metric, 0 when never recorded."""
    return registry.get_sample_value(name, {"shosai_loop_name": loop, **labels}) or 0.0


def iterations(registry: CollectorRegistry, loop: str, error: str) -> float:
    """Iterations of the loop that ended with the error type (empty: success)."""
    name = "shosai_loop_iteration_duration_seconds_count"
    return sample(registry, name, loop, error_type=error)


async def test_the_loop_metrics_follow_the_opentelemetry_naming_rules() -> None:
    registry, calls = CollectorRegistry(), Calls()
    runner = LoopRunner([ScheduledLoop("probe.named", QUICK, calls)], LoopMetrics(registry))

    runner.start()
    await eventually(lambda: calls.count >= 1)
    await runner.stop()

    recorded = {
        sample.name: set(sample.labels) - {"le"}
        for family in registry.collect()
        for sample in family.samples
        if not sample.name.endswith("_created")
    }
    assert recorded == {
        "shosai_loop_interval_seconds": {"shosai_loop_name"},
        "shosai_loop_last_success_timestamp_seconds": {"shosai_loop_name"},
        "shosai_loop_iteration_duration_seconds_bucket": {"shosai_loop_name", "error_type"},
        "shosai_loop_iteration_duration_seconds_count": {"shosai_loop_name", "error_type"},
        "shosai_loop_iteration_duration_seconds_sum": {"shosai_loop_name", "error_type"},
    }


async def test_a_loop_runs_at_start_then_once_per_interval() -> None:
    registry, calls = CollectorRegistry(), Calls()
    runner = LoopRunner([ScheduledLoop("probe.often", QUICK, calls)], LoopMetrics(registry))

    started = time.monotonic()
    runner.start()
    await eventually(lambda: calls.count >= 1)
    first_after = time.monotonic() - started
    await eventually(lambda: calls.count >= 4)
    await runner.stop()

    assert first_after < QUICK.total_seconds()
    assert sample(registry, "shosai_loop_interval_seconds", "probe.often") == 0.03
    assert sample(registry, "shosai_loop_last_success_timestamp_seconds", "probe.often") > 0
    assert iterations(registry, "probe.often", "") >= 4


async def test_a_failed_iteration_is_logged_with_its_stack_counted_and_survived() -> None:
    registry, calls = CollectorRegistry(), Calls(fail_first=2)
    runner = LoopRunner([ScheduledLoop("probe.flaky", QUICK, calls)], LoopMetrics(registry))

    with captured_logs() as captured:
        runner.start()
        await eventually(lambda: calls.count >= 3)
        await runner.stop()

    failures = [line for line in captured.lines() if line.get("loop") == "probe.flaky"]
    assert len(failures) == 2
    assert all("RuntimeError: итерация сломана нарочно" in line["exception"] for line in failures)
    assert iterations(registry, "probe.flaky", "RuntimeError") == 2
    assert sample(registry, "shosai_loop_last_success_timestamp_seconds", "probe.flaky") > 0


async def test_an_iteration_past_its_deadline_fails_and_the_loop_goes_on() -> None:
    registry, calls = CollectorRegistry(), Calls(hang_first=1)
    loop = ScheduledLoop("probe.stuck", QUICK, calls, deadline=QUICK)
    runner = LoopRunner([loop], LoopMetrics(registry))

    runner.start()
    await eventually(lambda: calls.count >= 2)
    await runner.stop()

    assert iterations(registry, "probe.stuck", "TimeoutError") == 1


async def test_stop_waits_for_the_iteration_in_progress_and_ends_every_loop() -> None:
    finished: list[str] = []

    async def slow() -> None:
        await asyncio.sleep(0.2)
        finished.append("slow")

    runner = LoopRunner(
        [ScheduledLoop("probe.slow", timedelta(hours=1), slow)], LoopMetrics(CollectorRegistry())
    )
    tasks = runner.start()
    await asyncio.sleep(0.05)
    await runner.stop()

    assert finished == ["slow"]
    assert all(task.done() for task in tasks)


def test_a_loop_name_is_stable_and_declared_once() -> None:
    calls = Calls()
    with pytest.raises(ValueError, match=r"срез\.цикл"):
        ScheduledLoop("Relay Outbox", QUICK, calls)
    with pytest.raises(ValueError, match="положительны"):
        ScheduledLoop("probe.zero", timedelta(0), calls)
    with pytest.raises(ValueError, match="дважды"):
        LoopRunner(
            [ScheduledLoop("probe.twice", QUICK, calls)] * 2, LoopMetrics(CollectorRegistry())
        )
