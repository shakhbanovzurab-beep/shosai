"""Readiness: 503 while starting or draining, 200 while ready whatever the dependencies say."""

import pytest

from shosai.core.health.probes import DependencyProbe
from shosai.core.health.readiness import ProcessPhase, Readiness


class ProbeFailedError(Exception):
    """The failure a probe declares."""


async def answers() -> None:
    """A dependency that answers."""


async def fails() -> None:
    """A dependency that is down."""
    raise ProbeFailedError


PROBES = (
    DependencyProbe("homes.ru", fails, (ProbeFailedError,)),
    DependencyProbe("homes.eu", answers, ()),
)


async def test_a_starting_process_is_not_ready_and_probes_nothing() -> None:
    readiness = Readiness()

    report = await readiness.report()

    assert (report.status, report.ready, report.dependencies) == (ProcessPhase.STARTING, False, {})


async def test_a_ready_process_stays_ready_with_a_dependency_down() -> None:
    readiness = Readiness()
    readiness.ready(PROBES)

    report = await readiness.report()

    assert report.ready
    assert report.dependencies == {"homes.ru": "down", "homes.eu": "ok"}


async def test_a_draining_process_is_not_ready_and_never_ready_again() -> None:
    readiness = Readiness()
    readiness.ready(PROBES)
    readiness.drain()
    readiness.drain()

    report = await readiness.report()

    assert (report.status, report.dependencies) == (ProcessPhase.DRAINING, {})
    with pytest.raises(RuntimeError, match="не может стать готовым"):
        readiness.ready(PROBES)
