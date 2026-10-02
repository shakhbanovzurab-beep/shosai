"""Readiness of a process: whether it takes work now, and how its dependencies answer (§3.11).

A process is not ready while it starts and while it drains; in between it is ready, even
when a dependency is down (F1-C2): every process shares the same dependencies, so failing
readiness on one would pull the whole plane from the edge, and EU users would lose
service over a Russian outage (§13.2). The report still names each dependency `ok` or
`down` for the operator; outages are alerted through metrics. Dependencies are probed only
while the process is ready: before that its clients do not exist, after it they close.
"""

from collections.abc import Mapping, Sequence
from enum import StrEnum

import structlog
from pydantic import BaseModel, ConfigDict

from whisperer.core.health.probes import DependencyProbe, ProbeStatus, probe_dependencies

log = structlog.stdlib.get_logger(__name__)


class ProcessPhase(StrEnum):
    """Where a process stands between its start and its exit."""

    STARTING = "starting"
    READY = "ready"
    DRAINING = "draining"


class ReadinessReport(BaseModel):
    """The phase of the process and the status of each dependency while it is ready."""

    model_config = ConfigDict(frozen=True)

    status: ProcessPhase
    dependencies: Mapping[str, ProbeStatus]

    @property
    def ready(self) -> bool:
        """Whether the process takes work."""
        return self.status is ProcessPhase.READY


class Readiness:
    """The phase of one process and the probes of its dependencies."""

    def __init__(self) -> None:
        self._phase = ProcessPhase.STARTING
        self._probes: tuple[DependencyProbe, ...] = ()

    @property
    def phase(self) -> ProcessPhase:
        """The current phase."""
        return self._phase

    def ready(self, probes: Sequence[DependencyProbe]) -> None:
        """The process has started and takes work; its dependencies are the given probes."""
        if self._phase is not ProcessPhase.STARTING:
            message = f"процесс в фазе {self._phase} не может стать готовым"
            raise RuntimeError(message)
        self._probes = tuple(probes)
        self._phase = ProcessPhase.READY
        log.info("Процесс готов к работе", dependencies=[probe.name for probe in self._probes])

    def drain(self) -> None:
        """The process stops taking work; it stays draining until it exits."""
        if self._phase is ProcessPhase.DRAINING:
            return
        self._phase = ProcessPhase.DRAINING
        log.info("Процесс перестаёт брать работу")

    async def report(self) -> ReadinessReport:
        """The phase and, while ready, every dependency's status."""
        if self._phase is not ProcessPhase.READY:
            return ReadinessReport(status=self._phase, dependencies={})
        statuses = await probe_dependencies(self._probes)
        # Фаза могла смениться, пока шли пробы: отчёт говорит о текущей.
        return ReadinessReport(status=self._phase, dependencies=statuses)
