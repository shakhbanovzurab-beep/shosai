"""The startup heap is frozen, so the collector's later passes skip it (ADR 0065)."""

import gc
import time

from shosai.core.runtime.heap import freeze_startup_heap


def full_pass_ms() -> float:
    """The shortest of three full passes of the cyclic collector, in milliseconds."""
    took = []
    for _ in range(3):
        started = time.perf_counter()
        gc.collect()
        took.append((time.perf_counter() - started) * 1000)
    return min(took)


def test_a_frozen_startup_heap_leaves_the_collectors_passes_short() -> None:
    before = full_pass_ms()
    try:
        frozen = freeze_startup_heap()
        after = full_pass_ms()
    finally:
        gc.unfreeze()

    assert frozen > 0
    assert after < before / 4
